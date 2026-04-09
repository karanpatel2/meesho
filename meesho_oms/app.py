"""
Meesho Order Management System — Flask Application Entry Point
"""
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from backend.routes.orders    import orders_bp
from backend.routes.stock     import stock_bp
from backend.routes.ocr_route import ocr_bp
from backend.routes.dashboard import dashboard_bp


def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join("frontend", "static"),
        template_folder=os.path.join("frontend", "templates"),
    )
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

    CORS(app)

    # Register blueprints
    app.register_blueprint(orders_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(ocr_bp)
    app.register_blueprint(dashboard_bp)

    # Serve frontend
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        from flask import render_template
        return render_template("index.html")

    return app


if __name__ == "__main__":
    app = create_app()
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug)
