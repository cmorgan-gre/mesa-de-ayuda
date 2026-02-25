from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory  # type: ignore
import sqlite3
import smtplib
from email.message import EmailMessage
import pandas as pd  # type: ignore
import io
from datetime import datetime
import os
from werkzeug.utils import secure_filename  # type: ignore

app = Flask(__name__)
DB = "tickets.db"

# ====== CONFIG ARCHIVOS ======
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}


def archivo_permitido(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ================== CONFIGURACIÓN DE CORREO ==================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "cmorgan@inphonity.com"
EMAIL_PASS = "tozyrfipwevypxws"

SOPORTE_EMAILS = [
    "cmorgan@inphonity.com",
    "jiturbe@inphonity.com",
]


def enviar_correo(destinatario, asunto, cuerpo):
    msg = EmailMessage()
    msg["From"] = EMAIL_USER
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content(cuerpo)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print(f"✅ Correo enviado a {destinatario}")
    except Exception as e:
        print(f"❌ Error al enviar correo: {e}")


# ================== CREAR BASE DE DATOS ==================
def init_db():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ejecutivo_nombre TEXT,
        ejecutivo_email TEXT,
        categoria TEXT,
        cliente_nombre TEXT,
        cliente_correo TEXT,
        dn_afectado TEXT,
        dn_contacto TEXT,
        rol TEXT,
        canal TEXT,
        link_genesys TEXT,
        descripcion_error TEXT,
        compania TEXT,
        numeros_prueba TEXT,
        numero_prueba TEXT,
        version_software TEXT,
        locucion TEXT,
        ubicacion TEXT,
        validaciones TEXT,
        tipo_afectacion TEXT,
        pagina_app TEXT,
        estatus TEXT DEFAULT 'Abierto'
    )
    """
    )

    for col in [
        "descripcion_solicitud",
        "descripcion_interaccion",
        "fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "fecha_cierre TIMESTAMP",
    ]:
        try:
            cursor.execute(f"ALTER TABLE tickets ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS comentarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER,
        comentario TEXT,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        remitente TEXT
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS adjuntos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER,
        nombre_archivo TEXT,
        ruta_archivo TEXT,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    conn.commit()
    conn.close()


init_db()

# ================== PÁGINAS ==================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/inicio_cc")
def inicio_cc():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tickets WHERE estatus='En proceso' ORDER BY id DESC")
    en_proceso = cursor.fetchall()

    cursor.execute("SELECT * FROM tickets WHERE estatus='Cerrado' ORDER BY id DESC")
    cerrados = cursor.fetchall()

    cursor.execute("SELECT * FROM tickets WHERE estatus='Abierto' ORDER BY id DESC")
    abiertos = cursor.fetchall()

    conn.close()
    return render_template(
        "inicio_cc.html",
        en_proceso=en_proceso,
        cerrados=cerrados,
        abiertos=abiertos,
    )


@app.route("/registro_interacciones")
def registro_interacciones():
    return render_template("registro_interacciones.html")


@app.route("/soporte")
def panel_soporte():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tickets WHERE estatus='Abierto' ORDER BY id DESC")
    abiertos = cursor.fetchall()

    cursor.execute("SELECT * FROM tickets WHERE estatus='En proceso' ORDER BY id DESC")
    en_proceso = cursor.fetchall()

    cursor.execute("SELECT * FROM tickets WHERE LOWER(estatus)='cerrado' ORDER BY id DESC")
    cerrados = cursor.fetchall()

    conn.close()

    return render_template(
        "soporte.html",
        abiertos=abiertos,
        en_proceso=en_proceso,
        cerrados=cerrados,
    )


@app.route("/soporte/ticket/<int:id>", methods=["GET", "POST"])
def soporte_detalle(id):
    remitente = "Inphonity"
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == "POST":
        comentario = request.form.get("comentario", "").strip()
        nuevo_estatus = request.form.get("estatus", "")

        if comentario:
            cursor.execute(
                "INSERT INTO comentarios (ticket_id, comentario, remitente) VALUES (?, ?, ?)",
                (id, comentario, remitente),
            )

        if nuevo_estatus:
            if nuevo_estatus.lower() == "cerrado":
                cursor.execute(
                    "UPDATE tickets SET estatus=?, fecha_cierre=CURRENT_TIMESTAMP WHERE id=?",
                    (nuevo_estatus, id),
                )
            else:
                cursor.execute(
                    "UPDATE tickets SET estatus=? WHERE id=?",
                    (nuevo_estatus, id),
                )

        conn.commit()
        conn.close()
        return redirect(url_for("soporte_detalle", id=id))

    cursor.execute("SELECT * FROM tickets WHERE id=?", (id,))
    ticket = cursor.fetchone()

    cursor.execute(
        "SELECT * FROM comentarios WHERE ticket_id=? ORDER BY id DESC",
        (id,),
    )
    comentarios = cursor.fetchall()

    cursor.execute("SELECT * FROM adjuntos WHERE ticket_id=?", (id,))
    adjuntos = cursor.fetchall()

    conn.close()

    return render_template(
        "soporte_detalle.html",
        ticket=ticket,
        comentarios=comentarios,
        adjuntos=adjuntos,
    )


# ================== CREAR TICKET ==================
@app.route("/crear_ticket", methods=["POST"])
def crear_ticket():
    datos = request.form.to_dict()

    def val(campo):
        v = datos.get(campo, "")
        if isinstance(v, list):
            return v[0] if v else ""
        return v

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    categoria_ticket = val("categoria")
    estatus_ticket = "Cerrado" if categoria_ticket.lower() == "interaccion" else "Abierto"

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fecha_cierre = ahora if estatus_ticket == "Cerrado" else None

    link = val("link")
    if link and not link.startswith("http"):
        link = "https://" + link

    cursor.execute(
        """
    INSERT INTO tickets (
        ejecutivo_nombre, ejecutivo_email, categoria,
        cliente_nombre, cliente_correo, dn_afectado, dn_contacto, rol, canal, link_genesys,
        descripcion_error, descripcion_solicitud, descripcion_interaccion,
        compania, numeros_prueba, numero_prueba, version_software, locucion,
        ubicacion, validaciones, tipo_afectacion, pagina_app, estatus,
        fecha_creacion, fecha_cierre
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,
        (
            val("ejecutivo_nombre"),
            val("ejecutivo_email"),
            categoria_ticket,
            val("cliente_nombre"),
            val("cliente_correo"),
            val("dn_afectado"),
            val("dn_contacto"),
            val("rol"),
            val("canal"),
            link,
            val("descripcion_error"),
            "",
            "",
            val("compania"),
            val("numeros_prueba"),
            val("numero_prueba"),
            val("version_software"),
            val("locucion"),
            val("ubicacion"),
            val("validaciones"),
            val("tipo_afectacion"),
            val("pagina_app"),
            estatus_ticket,
            ahora,
            fecha_cierre,
        ),
    )

    ticket_id = cursor.lastrowid

    # ===== GUARDAR ARCHIVOS =====
    if "evidencias" in request.files:
        archivos = request.files.getlist("evidencias")
        for archivo in archivos:
            if archivo and archivo.filename and archivo_permitido(archivo.filename):

                nombre_seguro = secure_filename(f"ticket_{ticket_id}_" + archivo.filename)
                ruta = os.path.join(app.config["UPLOAD_FOLDER"], nombre_seguro)

                archivo.save(ruta)

                # 🔥 CORRECCIÓN: guardar SOLO el nombre del archivo
                cursor.execute(
                    "INSERT INTO adjuntos (ticket_id, nombre_archivo, ruta_archivo) VALUES (?,?,?)",
                    (ticket_id, archivo.filename, nombre_seguro),
                )

    conn.commit()
    conn.close()
    # ===== ENVIAR CORREO A SOPORTE =====
    asunto = f"Nuevo Ticket #{ticket_id}"
    cuerpo = f"""
Se ha creado un nuevo ticket.

ID: {ticket_id}
Ejecutivo: {val("ejecutivo_nombre")}
Cliente: {val("cliente_nombre")}
Categoría: {categoria_ticket}
Descripción: {val("descripcion_error")}
"""

    for correo in SOPORTE_EMAILS:
        enviar_correo(correo, asunto, cuerpo)
    return redirect(url_for("ver_tickets"))


# ================== RESTO ==================
@app.route("/tickets")
def ver_tickets():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets ORDER BY id DESC")
    tickets = cursor.fetchall()
    conn.close()
    return render_template("tickets.html", tickets=tickets)


# 🔥 CORRECCIÓN IMPORTANTE (evita /uploads/uploads/)
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/descargar_db")
def descargar_db():
    return send_file(DB, as_attachment=True)


@app.route("/descargar_excel")
def descargar_excel():
    conn = sqlite3.connect(DB)

    df = pd.read_sql_query("SELECT * FROM tickets", conn)
    conn.close()

    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="tickets.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@app.route("/ticket/<int:id>", methods=["GET", "POST"])
def detalle_ticket(id):

    remitente = "Ejecutivo"

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ===== SI ENVÍAN FORMULARIO =====
    if request.method == "POST":

        comentario = request.form.get("comentario", "").strip()
        nuevo_estatus = request.form.get("estatus", "")

        if comentario:
            cursor.execute(
                "INSERT INTO comentarios (ticket_id, comentario, remitente) VALUES (?, ?, ?)",
                (id, comentario, remitente),
            )

        if nuevo_estatus:
            if nuevo_estatus.lower() == "cerrado":
                cursor.execute(
                    "UPDATE tickets SET estatus=?, fecha_cierre=CURRENT_TIMESTAMP WHERE id=?",
                    (nuevo_estatus, id),
                )
            else:
                cursor.execute(
                    "UPDATE tickets SET estatus=? WHERE id=?",
                    (nuevo_estatus, id),
                )

        conn.commit()
        conn.close()

        return redirect(url_for("detalle_ticket", id=id))

    # ===== CARGAR DATOS =====
    cursor.execute("SELECT * FROM tickets WHERE id=?", (id,))
    ticket = cursor.fetchone()

    cursor.execute(
        "SELECT * FROM comentarios WHERE ticket_id=? ORDER BY id DESC",
        (id,),
    )
    comentarios = cursor.fetchall()

    cursor.execute("SELECT * FROM adjuntos WHERE ticket_id=?", (id,))
    adjuntos = cursor.fetchall()

    conn.close()

    return render_template(
        "detalle_ticket.html",
        ticket=ticket,
        comentarios=comentarios,
        adjuntos=adjuntos,
    )



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
