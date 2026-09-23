"""Tests run on public builds in tests/fixtures (from pobb.in), never on the player's own builds in builds/.

POE2LAB_BUILDS points the build list (poe2lab.pobfiles.PROJECT_BUILDS) there before poe2lab is imported:
- titan: https://pobb.in/nbE_LaELwqqM (Furious Slam, Rage, Walking Calamity, Amor Mandragora) + a test profile;
- monk: https://pobb.in/vdObLGtT-Fx1 (Whirling Assault, energy shield and evasion);
- lich-minions: https://pobb.in/aWwyL0IiA1H- (a minion army);
- elemental-storm: https://pobb.in/cz7wG_YwPE4x (a main skill PoB computes 0 DPS for)."""
import os
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
os.environ["POE2LAB_BUILDS"] = str(FIXTURES)
