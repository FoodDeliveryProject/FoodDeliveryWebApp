let ws = null;
let orderCount = 0;
const countElement = document.querySelector(".new-order-count");
const resId = document.querySelector(".resid").getAttribute("id");
countElement.innerHTML = orderCount;

const wsProtocol = location.protocol === 'https' ? 'wss':'ws';
const wsUrl = `${wsProtocol}://${location.host}/ws/socket-server/${resId}/`;

const wsHandlers = {};

function connectWS(){
    ws = new WebSocket(wsUrl);

    ws.addEventListener('open',()=>{
        console.log("Connected to Merchant WS");
    })

    ws.addEventListener('close',()=>{
        console.warn("WS connection closed. Reconnecting in 5 sec......");
        setTimeout(connectWS,5000);
    })

    ws.addEventListener('error',(e)=>{
        showError({wsError:"WS error"},"error");
        console.error('WS error',e);
    })

    ws.addEventListener('message',onMessage);
}

function onMessage(evt) {
  try {
    const msg = JSON.parse(evt.data);

    if (msg.type === "status") {
        console.log("Server status:", msg.status);
    }

     if (msg.type === "chat") {
        orderCount++;
        countElement.innerHTML = orderCount;
        showNotification();
        document.title = `🔔 New Orders Received`;
        setTimeout(() => { document.title = "Orders"; }, 2000);
    }

    if(msg.type === "order_status_change"){
        const payload = msg.payload;
        showError({message:`Order ${payload.order_id} status updated to ${payload.new_status}!`})
    }

    if(msg.type === "deliveryman_accepted"){
        showError({message:`deliveryman "${msg.data.deliveryman.full_name}" has accepted order ${msg.data.order_id}`},"green");
      }
    Object.values(wsHandlers).forEach(handler => {
        try { handler(msg); } catch(e) { console.error("Handler error", e); }
    });
  } catch (e) {
    console.error('Invalid delivery WS message', e);
  }
}


function sendWSMessage(action, data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action, data : data }));
    }
}

function resetOrderCount() {
    orderCount = 0;
    countElement.innerHTML = 0;
    document.title = "Orders";
}

window.resetOrderCount = resetOrderCount;


function registerWSHandler(name, callback) {
    wsHandlers[name] = callback;
}

window.registerWSHandler = registerWSHandler;

window.addEventListener('DOMContentLoaded', connectWS);
