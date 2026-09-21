"""Read-only resume01 service boundary check for UI capture --service-check."""
from pathlib import Path
from service_generation import check_services

if Path(__file__).with_name('pause_new_scenes').exists():
    raise SystemExit('New scene queue paused for the confirmed HDR canvas-opacity defect; completed evidence preserved.')

if __name__ == '__main__':
    check_services('resume01')
    print('Recorded resume01 service owners remain active at this scene boundary.')
