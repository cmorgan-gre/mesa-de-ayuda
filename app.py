from flask_socketio import SocketIO, emit, join_room
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
# ⚡ Eventlet necesario para producción
socketio = SocketIO(
    app,
    async_mode="eventlet",
    cors_allowed_origins="https://tickets-inphonity.cloud"  # solo tu dominio
)


DB = "tickets.db"


usuarios_conectados = {}
EJECUTIVO_ROOMS = {
    "DAVID MORA": "david",
    "CESAR OCTAVIO SANTOS": "cesar",
    "FATIMA GUADALUPE MENDOZA SILIAS": "fatima",
    "VICTOR DE JESUS GOMEZ ZEA": "victor",
    "MANUEL ALEJANDRO GONZALEZ RIOS": "manuel"
}


from flask import session # type: ignore
from datetime import timedelta

app.secret_key = "TU_SECRETO_AQUI"  # obligatorio para usar sesiones
app.permanent_session_lifetime = timedelta(days=1)  # duración de la sesion


from functools import wraps
from flask import redirect, url_for # type: ignore

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            # Si no hay sesión activa, redirige al login
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function




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


USUARIOS = {
    
    "ejecutivo": {"password": "ejecutivo123", "rol": "ejecutivo"},
    "david": {"password": "ejecutivo123", "rol": "ejecutivo"},
    "cesar": {"password": "ejecutivo123", "rol": "ejecutivo"},
    "fatima": {"password": "ejecutivo123", "rol": "ejecutivo"},
    "victor": {"password": "ejecutivo123", "rol": "ejecutivo"},
    "manuel": {"password": "ejecutivo123", "rol": "ejecutivo"},

    "soporte": {"password": "soporte*123", "rol": "soporte"},
    "jesus": {"password": "jesus*123", "rol": "soporte"},
    "jaqueline": {"password": "jaqueline*123", "rol": "soporte"},
    "carlos": {"password": "carlos*123", "rol": "soporte"},
    "antonia": {"password": "Aruiz2026", "rol": "soporte"}
    
}

@socketio.on("connect")
def conectar():
    rol = session.get("rol")
    username = session.get("username")

    print("Nueva conexión socket:", username)

    if rol:
        join_room(rol)

    if username:
        join_room(username)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = USUARIOS.get(username)
        if user and user["password"] == password:
            session.permanent = True
            session["username"] = username
            session["rol"] = user["rol"]

            # Redirige según rol
            if user["rol"] == "soporte":
                return redirect(url_for("dashboard"))  # tu dashboard de soporte
            else:
                return redirect(url_for("inicio_cc"))  # inicio para ejecutivos y usuarios

        # Si falla
        return render_template("login.html", error="Usuario o contraseña incorrectos")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.clear()  # borra toda la sesión
    return redirect(url_for("login"))


from flask import session

@app.context_processor
def inject_rol():
    # Esto hace que la variable 'rol' esté disponible en todos los templates
    return dict(rol=session.get("rol"))


# ================== PÁGINAS ==================
@app.route("/")
@login_required
def index():
    return render_template("index.html")

# ================== inicio ==================
# ================== inicio ==================
@app.route("/inicio_cc")
@login_required
def inicio_cc():

    page = request.args.get("page", 1, type=int)
    por_pagina = 10
    offset = (page - 1) * por_pagina

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Tickets pendientes
    cursor.execute("SELECT * FROM tickets WHERE estatus='Pendiente' ORDER BY id DESC")
    pendiente = cursor.fetchall()


    # Tickets abiertos
    cursor.execute("SELECT * FROM tickets WHERE estatus='Abierto' ORDER BY id DESC")
    abiertos = cursor.fetchall()

    # Tickets en proceso
    cursor.execute("SELECT * FROM tickets WHERE estatus='En proceso' ORDER BY id DESC")
    en_proceso = cursor.fetchall()

    # ===== DATOS PARA LA GRAFICA =====
    cursor.execute("""
        SELECT ejecutivo_nombre, COUNT(*) as cant 
        FROM tickets 
        GROUP BY ejecutivo_nombre
    """)
    ejecutivos_data = cursor.fetchall()

    ejecutivos = [e["ejecutivo_nombre"] for e in ejecutivos_data]
    tickets_por_ejecutivo = [e["cant"] for e in ejecutivos_data]

    conn.close()


    # ===== IMAGENES DEL SLIDER =====
    carpeta = "static/img"

    imagenes = [
        img for img in os.listdir(carpeta)
        if img.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]

    imagenes = sorted(imagenes)

    return render_template(
        "inicio_cc.html",
        abiertos=abiertos,
        pendiente=pendiente,
        en_proceso=en_proceso,
        ejecutivos=ejecutivos,
        tickets_por_ejecutivo=tickets_por_ejecutivo,
        imagenes=imagenes
    )

@app.route("/registro_interacciones")
@login_required
def registro_interacciones():
    return render_template("registro_interacciones.html")

# Tickets SOPORTE 
@app.route("/soporte")
@login_required
def panel_soporte():
    page_cerrados = request.args.get("page_cerrados", 1, type=int)
    por_pagina = 10
    offset = (page_cerrados - 1) * por_pagina

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Tickets abiertos (todos)
    cursor.execute("SELECT * FROM tickets WHERE estatus='Abierto' ORDER BY id DESC")
    abiertos = cursor.fetchall()

    # Tickets en proceso (todos)
    cursor.execute("SELECT * FROM tickets WHERE estatus='En proceso' ORDER BY id DESC")
    en_proceso = cursor.fetchall()

    # Tickets cerrados con paginación
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE LOWER(estatus)='cerrado'")
    total_cerrados = cursor.fetchone()[0]
    total_paginas = (total_cerrados + por_pagina - 1) // por_pagina

    cursor.execute("""
        SELECT * FROM tickets 
        WHERE LOWER(estatus)='cerrado' 
        ORDER BY id DESC 
        LIMIT ? OFFSET ?
    """, (por_pagina, offset))
    cerrados = cursor.fetchall()

    conn.close()

    return render_template(
        "soporte.html",
        abiertos=abiertos,
        en_proceso=en_proceso,
        cerrados=cerrados,
        page_cerrados=page_cerrados,
        total_paginas_cerrados=total_paginas
    )

@app.route("/soporte/ticket/<int:id>", methods=["GET", "POST"])
@login_required
def soporte_detalle(id):
    remitente = session.get("username")
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == "POST":

        comentario = request.form.get("comentario", "").strip()
        nuevo_estatus = request.form.get("estatus", "")

        # Obtener estatus actual
        cursor.execute("SELECT estatus, ejecutivo_nombre FROM tickets WHERE id=?", (id,))
        ticket = cursor.fetchone()

        estatus_actual = ticket["estatus"]
        ejecutivo_nombre = ticket["ejecutivo_nombre"]

        ejecutivo = EJECUTIVO_ROOMS.get(ejecutivo_nombre)

        # ======================
        # GUARDAR COMENTARIO
        # ======================

        if comentario:
            cursor.execute(
                "INSERT INTO comentarios (ticket_id, comentario, remitente) VALUES (?, ?, ?)",
                (id, comentario, remitente),
            )

            # Notificar al ejecutivo
            if session.get("rol") == "soporte":
                socketio.emit(
                    "mensaje_ticket",
                    {
                        "ticket_id": id,
                        "mensaje": f"{remitente} respondió el ticket",
                        "tipo": "soporte"
                    },
                    room=ejecutivo
                )

        # ======================
        # CAMBIO DE ESTATUS
        # ======================

        if nuevo_estatus and nuevo_estatus != estatus_actual:

            if nuevo_estatus.lower() == "cerrado":
                from datetime import datetime
                ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute(
                    "UPDATE tickets SET estatus=?, fecha_cierre=? WHERE id=?",
                    (nuevo_estatus, ahora, id),
                )
            else:
                cursor.execute(
                    "UPDATE tickets SET estatus=? WHERE id=?",
                    (nuevo_estatus, id),
                )

            # 🔔 Notificar cambio de estatus
            socketio.emit(
                "estatus_ticket",
                {
                    "ticket_id": id,
                    "estatus": nuevo_estatus,
                    "mensaje": f"{remitente} cambió el estatus a {nuevo_estatus}"
                },
                room=ejecutivo
            )

        conn.commit()

        socketio.emit("actualizar_vista")



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






from datetime import datetime

@app.route("/dashboard")
@login_required
def dashboard():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Totales
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE estatus='Abierto'")
    total_abiertos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE estatus='En proceso'")
    total_en_proceso = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE estatus='Cerrado'")
    total_cerrados = cursor.fetchone()[0]

    # Tickets por categoría
    cursor.execute("SELECT categoria, COUNT(*) as cant FROM tickets GROUP BY categoria")
    categorias_data = cursor.fetchall()
    categorias = [c['categoria'] for c in categorias_data]
    tickets_por_categoria = [c['cant'] for c in categorias_data]

    # Tickets por ejecutivo
    cursor.execute("SELECT ejecutivo_nombre, COUNT(*) as cant FROM tickets GROUP BY ejecutivo_nombre")
    ejecutivos_data = cursor.fetchall()
    ejecutivos = [e['ejecutivo_nombre'] for e in ejecutivos_data]
    tickets_por_ejecutivo = [e['cant'] for e in ejecutivos_data]

    # Evolución de tickets últimos 30 días
    cursor.execute("""
        SELECT DATE(fecha_creacion) as fecha, COUNT(*) as cant 
        FROM tickets 
        WHERE fecha_creacion >= DATE('now', '-29 days')
        GROUP BY fecha
        ORDER BY fecha
    """)
    fechas_data = cursor.fetchall()
    fechas = [f['fecha'] for f in fechas_data]
    tickets_por_fecha = [f['cant'] for f in fechas_data]

    # ----- Tiempo promedio de resolución -----
    cursor.execute("""
        SELECT fecha_creacion, fecha_cierre
        FROM tickets
        WHERE fecha_cierre IS NOT NULL
    """)
    tickets_cerrados = cursor.fetchall()

    total_segundos = 0
    for t in tickets_cerrados:
        inicio = datetime.fromisoformat(t['fecha_creacion'])
        fin = datetime.fromisoformat(t['fecha_cierre'])
        total_segundos += (fin - inicio).total_seconds()

    promedio_segundos = 0
    if tickets_cerrados:
        promedio_segundos = total_segundos / len(tickets_cerrados)

    horas = int(promedio_segundos // 3600)
    minutos = int((promedio_segundos % 3600) // 60)
    segundos = int(promedio_segundos % 60)
    tiempo_promedio = f"{horas}h {minutos}m {segundos}s"

    # ===== Duración de tickets cerrados =====
    cursor.execute("""
        SELECT id, fecha_creacion, fecha_cierre
        FROM tickets
        WHERE fecha_cierre IS NOT NULL
    """)

    duracion_data = cursor.fetchall()

    duraciones = []
    labels_duracion = []

    for t in duracion_data:
        inicio = datetime.fromisoformat(t['fecha_creacion'])
        fin = datetime.fromisoformat(t['fecha_cierre'])

        minutos = round((fin - inicio).total_seconds() / 60, 2)

        duraciones.append(minutos)
        labels_duracion.append(f"Ticket {t['id']}")



    # ===== Duración de tickets activos =====
    cursor.execute("""
        SELECT id, fecha_creacion
        FROM tickets
        WHERE estatus != 'Cerrado'
    """)

    tickets_activos = cursor.fetchall()

    labels_activos = []
    tiempos_activos = []
    fechas_creacion_activos = []

    ahora = datetime.now()

    for t in tickets_activos:
        inicio = datetime.fromisoformat(t['fecha_creacion'])
        minutos = round((ahora - inicio).total_seconds() / 3600, 2)

        labels_activos.append(f"Ticket {t['id']}")
        tiempos_activos.append(minutos)
        fechas_creacion_activos.append(t['fecha_creacion'])

        
    conn.close()

    return render_template(
        "dashboard.html",
        total_abiertos=total_abiertos,
        total_en_proceso=total_en_proceso,
        total_cerrados=total_cerrados,
        categorias=categorias,
        tickets_por_categoria=tickets_por_categoria,
        ejecutivos=ejecutivos,
        tickets_por_ejecutivo=tickets_por_ejecutivo,
        fechas=fechas,
        tickets_por_fecha=tickets_por_fecha,
        tiempo_promedio=tiempo_promedio,
        duraciones=duraciones,
        labels_duracion=labels_duracion,
        labels_activos=labels_activos,
        tiempos_activos=tiempos_activos,
        fechas_creacion_activos=fechas_creacion_activos
    )




# ================== CREAR TICKET ==================
@app.route("/crear_ticket", methods=["POST"])
@login_required
def crear_ticket():
    accion = request.form.get("accion")
    datos = request.form.to_dict()

    def val(campo):
        v = datos.get(campo, "")
        if isinstance(v, list):
            return v[0] if v else ""
        return v

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    categoria_ticket = val("categoria")

    accion = request.form.get("accion")
    if accion == "n2":
        estatus_ticket = "Abierto"
    elif accion == "cerrar":
        estatus_ticket = "Cerrado"
    elif accion == "pendiente":
        estatus_ticket = "Pendiente"
    else:
        estatus_ticket = "Abierto"

    

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
            val("descripcion_solicitud"),
            val("descripcion_interaccion"),
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

    socketio.emit("actualizar_vista")


    socketio.emit(
        "nuevo_ticket",
        {
            "ticket_id": ticket_id,
            "estatus": estatus_ticket,
            "mensaje": "Nuevo ticket creado"
        },
        room="soporte"
    )

    conn.close()

    return redirect(url_for("ver_tickets"))

    return redirect(url_for("ver_tickets"))


# ================== tickets ==================
@app.route("/tickets")
@login_required
def ver_tickets():

    page = request.args.get("page", 1, type=int)
    buscar = request.args.get("buscar", "")
    categoria = request.args.get("categoria", "")
    estatus = request.args.get("estatus", "")
    ejecutivo_nombre = request.args.get("ejecutivo_nombre", "")

    por_pagina = 10
    offset = (page - 1) * por_pagina

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ===== QUERY BASE =====
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []

    # ===== BUSCADOR =====
    if buscar:
        query += """
        AND (
            id LIKE ?
            OR categoria LIKE ?
            OR cliente_nombre LIKE ?
            OR cliente_correo LIKE ?
            OR dn_afectado LIKE ?
            OR dn_contacto LIKE ?
        )
        """
        like = f"%{buscar}%"
        params.extend([like, like, like, like, like, like])

    # ===== FILTRO CATEGORIA =====
    if categoria:
        query += " AND categoria=?"
        params.append(categoria)

    # ===== FILTRO ESTATUS =====
    if estatus:
        query += " AND estatus=?"
        params.append(estatus)

     # ===== FILTRO EJECUTIVO =====
    if ejecutivo_nombre:
        query += " AND TRIM(ejecutivo_nombre)=TRIM(?)"
        params.append(ejecutivo_nombre)   
    

    # ===== CONTAR TOTAL =====
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # ===== PAGINACION =====
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([por_pagina, offset])

    cursor.execute(query, params)
    tickets = cursor.fetchall()

    conn.close()

    total_paginas = (total + por_pagina - 1) // por_pagina

    return render_template(
        "tickets.html",
        tickets=tickets,
        page=page,
        total_paginas=total_paginas,
        buscar=buscar,
        categoria=categoria,
        ejecutivo_nombre=ejecutivo_nombre,
        estatus=estatus
    )




# 🔥 CORRECCIÓN IMPORTANTE (evita /uploads/uploads/)
@app.route("/uploads/<path:filename>")
@login_required
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
@login_required
def detalle_ticket(id):
    accion = request.form.get("accion")

    remitente = session.get("username")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()




    # ===== SI ENVÍAN FORMULARIO =====
    if request.method == "POST":

        comentario = request.form.get("comentario", "").strip()
        accion = request.form.get("accion")

        if comentario:
            cursor.execute(
                "INSERT INTO comentarios (ticket_id, comentario, remitente) VALUES (?, ?, ?)",
                (id, comentario, remitente),
            )
        if session.get("rol") == "ejecutivo":
            socketio.emit(
                "mensaje_ticket",
                {
                    "ticket_id": id,
                    "mensaje": f"{remitente} agregó un comentario",
                    "tipo": "ejecutivo"
                },
                room="soporte"
            )

        # ===== BOTONES DE ACCION =====
        if accion == "cerrar":
            from datetime import datetime
            ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(
                "UPDATE tickets SET estatus=?, fecha_cierre=? WHERE id=?",
                ("Cerrado", ahora, id),
            )

        elif accion == "n2":
            cursor.execute(
                "UPDATE tickets SET estatus=? WHERE id=?",
                ("Abierto", id),
            )
        elif accion == "pendiente":
            cursor.execute(
                "UPDATE tickets SET estatus=? WHERE id=?",
                ("Pendiente", id),
            )
        conn.commit()

        socketio.emit("actualizar_vista")

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
import pandas as pd





if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=443,
        ssl_context=("cert.pem", "key.pem"),
        debug=True
    )
