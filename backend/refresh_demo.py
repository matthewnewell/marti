"""Re-apply the demo manufacturing data (Radar Housing + Nacelle materials, routings, orders and
Tradeoffs) to the CURRENT database. Idempotent.

    cd backend && .venv/bin/python refresh_demo.py
"""

from app import create_app
from demo_data import apply_demo_materials

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print({"materials_added": apply_demo_materials()})
