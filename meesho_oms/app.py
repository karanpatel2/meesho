import os
from flask import Flask, send_from_directory
from flask_cors import CORS

from backend.routes.orders    import orders_bp
from backend.routes.stock     import stock_bp
from backend.routes.ocr_route import ocr_bp
from backend.routes.dashboard import dashboard_bp
from backend.routes.auth      import auth_bp


def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join("frontend", "static"),
        template_folder=os.path.join("frontend", "templates"),
    )
    app.secret_key = "meesho-oms-secret-2024"
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    CORS(app)

    # Database folder banao agar nahi hai
    db_folder = os.path.join(os.path.dirname(__file__), "database")
    os.makedirs(db_folder, exist_ok=True)

    # DB initialize karo - tables banao
    from backend.db import init_db
    init_db()

    # Blueprints register karo
    app.register_blueprint(auth_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(ocr_bp)
    app.register_blueprint(dashboard_bp)

    # Frontend serve karo
# Serve frontend
    @app.route("/login")
    def login_page():
        from flask import render_template, session, redirect
        if session.get("user_id"):
            return redirect("/")
        return render_template("login.html")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        from flask import render_template, session, redirect
        if not session.get("user_id"):
            return redirect("/login")
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return render_template("index.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)

app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response