"""Read-only service ownership boundary for the fixed Viser client generation."""
from pathlib import Path
from service_generation import check_services

if __name__ == '__main__':
    if Path(__file__).with_name('pause_new_scenes').exists():
        raise SystemExit('New scene queue paused while fixed client validation is pending.')
    check_services('resume02')
    print('Recorded resume02 service owners remain active at this scene boundary.')
