
console.log("🔌 iniciando manager.js...");

/* =========================
   CONEXION SOCKET
========================= */

const socket = io("https://tickets-inphonity.cloud", {
    path: "/socket.io",
    transports: ["websocket", "polling"], // polling como fallback
    secure: true
});
socket.on("connect", function(){
    console.log("✅ Socket conectado:", socket.id);
});

socket.on("connect_error", function(err){
    console.log("❌ Error socket:", err);
});


/* =========================
   PERMISO NOTIFICACIONES
========================= */

if ("Notification" in window) {

    Notification.requestPermission().then(function(permission){
        console.log("🔔 Permiso notificaciones:", permission);
    });

}


/* =========================
   NUEVO TICKET
   (solo soporte recibe)
========================= */

socket.on("nuevo_ticket", function(data){

    console.log("🎫 Nuevo ticket:", data);

    /* SOLO notificar si está en Abierto */
    if(data.estatus !== "Abierto"){
        return;
    }

    if (Notification.permission === "granted") {

        let n = new Notification("🎫 Nuevo ticket creado", {
            body: "Ticket #" + data.ticket_id + " requiere atención",
            icon: "/static/img/logo.png"
        });

        n.onclick = function(){
            window.open("/soporte/ticket/" + data.ticket_id);
        };

    }

});


/* =========================
   MENSAJE EN TICKET
========================= */

socket.on("mensaje_ticket", function(data){

    console.log("💬 Mensaje ticket:", data);

    if (Notification.permission === "granted") {

        let n = new Notification("💬 Actualización en ticket", {
            body: data.mensaje + " (#" + data.ticket_id + ")",
            icon: "/static/img/logo.png"
        });

        if(data.tipo === "soporte"){

            /* soporte respondió -> ejecutivo abre ticket */
            n.onclick = function(){
                window.open("/ticket/" + data.ticket_id);
            };

        }else{

            /* ejecutivo respondió -> soporte abre ticket */
            n.onclick = function(){
                window.open("/soporte/ticket/" + data.ticket_id);
            };

        }

    }

});


/* =========================
   CAMBIO DE ESTATUS
========================= */

socket.on("estatus_ticket", function(data){

    console.log("📌 Estatus ticket:", data);

    if (Notification.permission === "granted") {

        let n = new Notification("📌 Ticket actualizado", {
            body: "Ticket #" + data.ticket_id + " ahora está: " + data.estatus,
            icon: "/static/img/logo.png"
        });

        n.onclick = function(){
            window.open("/ticket/" + data.ticket_id);
        };

    }

});

socket.on("actualizar_vista", function(){

    console.log("🔄 actualizando vista");

    location.reload();

});
