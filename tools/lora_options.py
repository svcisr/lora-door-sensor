"""Regenerate the data in docs/lora-options.html (the LoRa option comparison page).

Computes, for every SF7-12 x BW 125/250/500 kHz x 10/14/17/20/22 dBm combination and the
door packet: airtime, charge per transmission, average sensor current, battery life,
sensitivity, link budget and rough range. The "now" marker and default TX interval are read
from include/config.h, so the page follows the firmware settings.

  python tools/lora_options.py            update docs/lora-options.html
  python tools/lora_options.py --print    also print the 125 kHz rows

After updating, republish the page if it is shared as an artifact.
"""
import argparse
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = ROOT / "include" / "config.h"
PAGE = ROOT / "docs" / "lora-options.html"

PAYLOAD = 10          # bytes, see src/common/door_protocol.h
PREAMBLE = 8
CR = 1                # 4/5
CRC = 1
IMPLICIT = 0
REF_PERIOD_S = 5.0    # stored rows use this; the page recalculates for its interval input
FREQ = 433.5e6
BATTERY_MAH = 2000.0

# SX1262 TX current with optimal PA settings (datasheet table 13-21); 10 dBm is not listed -> estimate
TX_MA = {22: (118, False), 20: (102, False), 17: (95, False), 14: (90, False), 10: (55, True)}
MCU_ACTIVE_MA = 20.0        # STM32F103 at 64 MHz, estimate
# Battery current while transmitting, measured on the Otii at 3.7 V into the TPS63802
# (2026-10-25). Other powers use the datasheet radio current + MCU_ACTIVE_MA (at 3.3 V, about 3%
# above the battery current at 3.7 V).
MEASURED_TX_BOARD_MA = {22: 140}
MCU_OVERHEAD_MS = 12.0      # wake, clock restore, radio wake + trim, ADC, log
LED_MA = 2.0                # estimate
LED_FLASH_MS = 20.0         # SENSOR_LED_FLASH_MS, fixed flash per packet
# Measured 2026-10-25 at the battery: Otii at 3.7 V into the TPS63802 (board 1: CH340, POW LED
# resistor and AMS1117 removed, RXEN fix, SX1262 asleep). Written into the page as well.
SLEEP_UA = 31.0
ANT_GAIN_DBI = 2.0
FADE_MARGIN_DB = 10.0
ANT_HEIGHT_M = 1.5
NOISE_FIGURE_DB = 6.0
SNR_LIMIT = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}


def airtime_ms(sf, bw_hz):
    tsym = (2 ** sf) / bw_hz * 1000.0
    ldro = 1 if tsym >= 16.0 else 0
    t_pre = (PREAMBLE + 4.25) * tsym
    num = 8 * PAYLOAD - 4 * sf + 28 + 16 * CRC - 20 * IMPLICIT
    n_payload = 8 + max(math.ceil(num / (4 * (sf - 2 * ldro))) * (CR + 4), 0)
    return t_pre + n_payload * tsym, ldro


def sensitivity_dbm(sf, bw_hz):
    return -174 + 10 * math.log10(bw_hz) + NOISE_FIGURE_DB + SNR_LIMIT[sf]


def range_open_m(link_budget):
    """Two-ray ground reflection, both antennas at ANT_HEIGHT_M."""
    loss = link_budget - FADE_MARGIN_DB
    return 10 ** ((loss + 20 * math.log10(ANT_HEIGHT_M * ANT_HEIGHT_M)) / 40)


def range_urban_m(link_budget, n=4.0):
    """Log-distance model from a 1 m free-space reference, exponent n (buildings, walls)."""
    pl_1m = 20 * math.log10(4 * math.pi * FREQ / 3e8)
    loss = link_budget - FADE_MARGIN_DB
    return 10 ** ((loss - pl_1m) / (10 * n))


def compute_rows():
    rows = []
    for power, (radio_ma, radio_est) in TX_MA.items():
        measured = power in MEASURED_TX_BOARD_MA
        tx_ma = MEASURED_TX_BOARD_MA[power] if measured else radio_ma + MCU_ACTIVE_MA
        tx_est = radio_est and not measured
        for bw in (125e3, 250e3, 500e3):
            for sf in range(7, 13):
                t_ms, ldro = airtime_ms(sf, bw)
                cycle_mas = (tx_ma * t_ms + MCU_ACTIVE_MA * MCU_OVERHEAD_MS
                             + LED_MA * LED_FLASH_MS) / 1000
                avg_ma = cycle_mas / REF_PERIOD_S + SLEEP_UA / 1000
                sens = sensitivity_dbm(sf, bw)
                budget = power + 2 * ANT_GAIN_DBI - sens
                rows.append({
                    "power": power, "txMa": round(tx_ma), "txEst": tx_est, "txMeas": measured,
                    "bw": int(bw / 1000), "sf": sf, "ldro": ldro,
                    "bitrate": round(sf * (bw / 2 ** sf) * 4 / (4 + CR)),
                    "airtimeMs": round(t_ms, 1),
                    "dutyPct": round(t_ms / (REF_PERIOD_S * 1000) * 100, 2),
                    "chargePerTxMas": round(cycle_mas, 2),
                    "avgUa": round(avg_ma * 1000),
                    "batteryDays": round(BATTERY_MAH / avg_ma / 24),
                    "sensitivity": round(sens, 1),
                    "linkBudget": round(budget, 1),
                    "rangeOpenM": round(range_open_m(budget), -1),
                    "rangeUrbanM": round(range_urban_m(budget), -1),
                })
    return rows


def read_config():
    text = CONFIG.read_text(encoding="utf-8")

    def define(name):
        m = re.search(rf"#define\s+{name}\s+([0-9.]+)", text)
        if not m:
            sys.exit(f"{name} not found in {CONFIG}")
        return float(m.group(1))

    return {
        "sf": int(define("LORA_SF")),
        "bw": int(define("LORA_BW_KHZ")),
        "power": int(define("LORA_TX_POWER_DBM")),
        "interval": int(define("TX_PERIOD_MS") // 1000),
    }


def update_page(rows, cfg):
    html = PAGE.read_text(encoding="utf-8")
    replacements = [
        (r"const ROWS = \[.*?\];", "const ROWS = " + json.dumps(rows) + ";"),
        (r"const CURRENT = \{[^}]*\};",
         f"const CURRENT = {{ power: {cfg['power']}, bw: {cfg['bw']}, sf: {cfg['sf']} }};"),
        (r'(<input id="interval"[^>]*value=")\d+(")', rf"\g<1>{cfg['interval']}\g<2>"),
        (r"const SLEEP_UA = [\d.]+;", f"const SLEEP_UA = {SLEEP_UA:g};"),
        (r'(<span class="label">Sleep floor</span><span class="num">)[\d.]+( µA</span>)',
         rf"\g<1>{SLEEP_UA:g}\g<2>"),
        (r"(÷ interval \+ )[\d.]+(&nbsp;µA sleep floor)", rf"\g<1>{SLEEP_UA:g}\g<2>"),
    ]
    for pattern, new in replacements:
        html, n = re.subn(pattern, lambda _m, new=new: _m.expand(new) if "\\g<" in new else new,
                          html, count=1, flags=re.S)
        if n != 1:
            sys.exit(f"pattern not found in {PAGE}: {pattern}")
    PAGE.write_text(html, encoding="utf-8", newline="\n")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--print", action="store_true", help="print the 125 kHz rows")
    args = p.parse_args()

    rows = compute_rows()
    cfg = read_config()
    update_page(rows, cfg)
    print(f"Updated {PAGE.relative_to(ROOT)}: {len(rows)} options, current "
          f"SF{cfg['sf']} / {cfg['bw']} kHz / {cfg['power']} dBm, interval {cfg['interval']} s")

    if args.print:
        for r in rows:
            if r["bw"] == 125:
                print(f"{r['power']:>2} dBm SF{r['sf']:>2}: {r['airtimeMs']:>7.1f} ms  {r['avgUa']:>6} uA  "
                      f"{r['batteryDays']:>4} d  LB {r['linkBudget']}  "
                      f"open {r['rangeOpenM'] / 1000:.1f} km  urban {r['rangeUrbanM'] / 1000:.2f} km")
    return 0


if __name__ == "__main__":
    sys.exit(main())
