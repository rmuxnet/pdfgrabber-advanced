import json
import configparser
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file
from tinydb import Query
from .. import utils
from .. import config as configmod
import threading

app = Flask(__name__)


@app.template_filter("regex_match")
def regex_match_filter(value, pattern):
    import re
    return bool(re.fullmatch(pattern, str(value)))



def _get_or_create_web_user_id():
    user = utils.usertable.get(Query().name == "webui")
    if user:
        return user.doc_id
    
    return utils.register("webui", "webui_password_placeholder")


def _get_token_for_service(service):
    if service in utils.nologin:
        return "dummy", None

    userid = _get_or_create_web_user_id()
    token = None

    if userid is not None:
        token = utils.gettoken(userid, service)
    if not token:
        token = utils.gettoken(None, service)

    if not token:
        return None, f"No token found for '{service}'. Please log in via the web interface."

    try:
        valid = utils.checktoken(service, token)
        if not valid:
            refreshed = utils.refreshtoken(service, token)
            if refreshed:
                if userid is not None:
                    utils.addtoken(userid, service, refreshed)
                token = refreshed
            else:
                return None, f"Token for '{service}' is expired and could not be refreshed. Please log in via the web interface."
    except Exception:
        pass  # Some services may not implement checktoken fully

    return token, None


def _read_config_data():
    cfg = configmod.getconfig()
    confpath = Path("config.ini")

    raw_sections = []
    if cfg.has_section("pdfgrabber"):
        raw_sections.append("pdfgrabber")
    raw_sections.append("DEFAULT")
    for s in sorted(cfg.sections()):
        if s not in raw_sections:
            raw_sections.append(s)

    raw_comments = {}
    if confpath.is_file():
        current_section = None
        pending = []
        for line in confpath.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and "]" in stripped:
                current_section = stripped[1:stripped.index("]")]
                pending = []
            elif stripped.startswith("#") or stripped.startswith(";"):
                pending.append(stripped.lstrip("#; ").strip())
            elif "=" in stripped and current_section is not None:
                key = stripped.split("=", 1)[0].strip()
                if pending:
                    raw_comments.setdefault(current_section, {})[key] = " ".join(pending)
                pending = []
            else:
                pending = []

    config_data = {}
    for section in raw_sections:
        items = {}
        if section == "DEFAULT":
            for k, v in cfg.defaults().items():
                items[k] = v
        elif cfg.has_section(section):
            for k in cfg.options(section):
                items[k] = cfg.get(section, k)
        config_data[section] = items

    return config_data, raw_sections, raw_comments



@app.route("/")
def index():
    return render_template("index.html", services=utils.services, active_nav="services")


@app.route("/library/<service>")
def library(service):
    if service not in utils.services:
        return render_template("library.html", service=service, books={},
                               error=f"Unknown service '{service}'.", active_nav="services")

    token, error = _get_token_for_service(service)
    if error:
        return render_template("library.html", service=service, books={},
                               error=error, active_nav="services")

    try:
        books = utils.library(service, token)
        if books is None:
            books = {}
        return render_template("library.html", service=service, books=books,
                               active_nav="services")
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        return render_template("library.html", service=service, books={},
                               error=f"{e}\n\n{trace}", active_nav="services")


@app.route("/downloads")
def downloads():
    raw_books = utils.listbooks()
    books = []
    for doc in raw_books:
        books.append({
            "service": doc.get("service", ""),
            "bookid": doc.get("bookid", ""),
            "title": doc.get("title", "Untitled"),
            "pages": doc.get("pages", 0),
            "path": doc.get("path", ""),
        })

    total_pages = sum(b["pages"] for b in books)
    service_set = sorted(set(b["service"] for b in books if b["service"]))

    return render_template(
        "downloads.html",
        books=books,
        books_json=json.dumps(books, default=str),
        total_pages=total_pages,
        service_count=len(service_set),
        service_list=service_set,
        active_nav="downloads",
    )


@app.route("/settings")
def settings():
    config_data, sections, comments = _read_config_data()
    config_json = json.dumps({s: dict(opts) for s, opts in config_data.items()})

    return render_template(
        "settings.html",
        config_data=config_data,
        config_json=config_json,
        sections=sections,
        comments=comments,
        services=utils.services,
        active_nav="settings",
    )


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        confpath = Path("config.ini")

        cfg = configparser.ConfigParser()
        if confpath.is_file():
            cfg.read(confpath, encoding="utf-8")

        for section, options in data.items():
            if section == "DEFAULT":
                for k, v in options.items():
                    cfg.defaults()[k] = str(v)
            else:
                if not cfg.has_section(section):
                    cfg.add_section(section)
                for k, v in options.items():
                    cfg.set(section, k, str(v))

        original_lines = []
        if confpath.is_file():
            original_lines = confpath.read_text(encoding="utf-8").splitlines()

        _write_config_preserving_comments(confpath, cfg, data, original_lines)

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _write_config_preserving_comments(confpath, cfg, new_data, original_lines):
    comment_map = {}        # (section, key) -> [lines_before_key]
    section_comments = {}   # section -> [lines_before_section_header]
    current_section = None
    pending = []

    for line in original_lines:
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith(";") or stripped == "":
            pending.append(line)
        elif stripped.startswith("[") and "]" in stripped:
            sec = stripped[1:stripped.index("]")]
            section_comments[sec] = list(pending)
            pending = []
            current_section = sec
        elif "=" in stripped and current_section is not None:
            key = stripped.split("=", 1)[0].strip()
            if pending:
                comment_map[(current_section, key)] = list(pending)
            pending = []
        else:
            pending = []

    section_order = []
    if "pdfgrabber" in new_data:
        section_order.append("pdfgrabber")
    if "DEFAULT" in new_data:
        section_order.append("DEFAULT")
    for s in sorted(new_data.keys()):
        if s not in section_order:
            section_order.append(s)

    out = []
    for section in section_order:
        if section in section_comments:
            out.extend(section_comments[section])

        out.append(f"[{section}]")

        opts = new_data.get(section, {})
        for key, val in opts.items():
            if (section, key) in comment_map:
                out.extend(comment_map[(section, key)])
            out.append(f"{key} = {val}")

        out.append("")

    confpath.write_text("\n".join(out), encoding="utf-8")


@app.route("/file/<service>/<bookid>")
def serve_file(service, bookid):
    path = Path("files") / service / f"{bookid}.pdf"
    if path.is_file():
        return send_file(str(path.resolve()), mimetype="application/pdf")
    return "File not found", 404


progress_dir = Path("files/.progress")
progress_dir.mkdir(parents=True, exist_ok=True)

def set_progress(service, bookid, perc, msg=""):
    progress_file = progress_dir / f"{service}_{bookid}.json"
    progress_file.write_text(json.dumps({"perc": perc, "msg": msg}), encoding="utf-8")

def get_progress(service, bookid):
    progress_file = progress_dir / f"{service}_{bookid}.json"
    if progress_file.is_file():
        try:
            return json.loads(progress_file.read_text(encoding="utf-8"))
        except Exception:
            return {"perc": 0, "msg": ""}
    return {"perc": 0, "msg": ""}

def clear_progress(service, bookid):
    progress_file = progress_dir / f"{service}_{bookid}.json"
    if progress_file.is_file():
        progress_file.unlink()

@app.route("/api/progress/<service>/<bookid>")
def api_progress(service, bookid):
    return jsonify(get_progress(service, bookid))


@app.route("/api/login/<service>", methods=["POST"])
def api_login(service):
    if service not in utils.services:
        return jsonify({"ok": False, "error": "Unknown service"}), 404
        
    data = request.get_json() or {}
    token_input = data.get("token")
    username = data.get("username")
    password = data.get("password")
    
    if not token_input and (not username or not password):
        return jsonify({"ok": False, "error": "Either token or username/password required"}), 400
        
    try:
        if token_input:
            if not utils.checktoken(service, token_input):
                return jsonify({"ok": False, "error": "The provided token is invalid"}), 401
            token = token_input
        else:
            token = utils.login(service, username, password)
            if not token:
                return jsonify({"ok": False, "error": "Invalid credentials or login failed"}), 401
            
        userid = _get_or_create_web_user_id()
        if userid is not None:
            utils.addtoken(userid, service, token)
            return jsonify({"ok": True, "message": "Logged in successfully"})
        else:
            return jsonify({"ok": False, "error": "Failed to retrieve web user"}), 500
    except Exception as e:
        import sys
        print(f"[DEBUG] Exception during login: {e}", file=sys.stderr)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/download/<service>/<bookid>", methods=["POST"])
def api_download(service, bookid):
    import sys
    print(f"[DEBUG] Download API called for service={service} bookid={bookid}", file=sys.stderr)
    if service not in utils.services:
        print("[DEBUG] Unknown service", file=sys.stderr)
        return jsonify({"ok": False, "error": "Unknown service"}), 404

    token, error = _get_token_for_service(service)
    if error:
        print(f"[DEBUG] Token error: {error}", file=sys.stderr)
        return jsonify({"ok": False, "error": error}), 400

    try:
        books = utils.library(service, token)
        print(f"[DEBUG] Library loaded, keys: {list(books.keys())}", file=sys.stderr)
        if not books or bookid not in books:
            print("[DEBUG] Book not found in library", file=sys.stderr)
            return jsonify({"ok": False, "error": "Book not found in library"}), 404

        def progress_callback(perc, msg=""):
            set_progress(service, bookid, perc, msg)
            print(f"[DEBUG] Download progress: {perc}% {msg}", file=sys.stderr)

        def download_task():
            try:
                pdfpath = utils.downloadbook(service, token, bookid, books[bookid], progress_callback)
                progress_file = progress_dir / f"{service}_{bookid}.json"
                progress_file.write_text(json.dumps({"perc": 100, "msg": "Done", "ok": True, "path": str(pdfpath)}), encoding="utf-8")
                print(f"[DEBUG] Download finished, path: {pdfpath}", file=sys.stderr)
            except Exception as exc:
                print(f"[DEBUG] Exception during async download: {exc}", file=sys.stderr)
                progress_file = progress_dir / f"{service}_{bookid}.json"
                progress_file.write_text(json.dumps({"perc": 100, "msg": str(exc), "ok": False, "error": str(exc)}), encoding="utf-8")

        clear_progress(service, bookid)
        
        set_progress(service, bookid, 0, "Starting download...")
        
        threading.Thread(target=download_task, daemon=True).start()
        
        return jsonify({"ok": True, "status": "started"})
    except Exception as e:
        print(f"[DEBUG] Exception launching download: {e}", file=sys.stderr)
        clear_progress(service, bookid)
        return jsonify({"ok": False, "error": str(e)}), 500


def run_server():
    app.run(debug=False, use_reloader=False)

