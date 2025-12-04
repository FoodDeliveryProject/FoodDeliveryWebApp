let ws = null;

let newDeliveryCount = 0;
const countElement = document.querySelector(".new-order-count");
const deliveryman_id = document.querySelector(".delid").getAttribute("id");
countElement.innerHTML = newDeliveryCount;

let deliverymanStatus = "IDLE";
let currentOrderIds = [];
let locationInterval = null;
let lastLocation = { lat: null, lng: null, accuracy: null };


const wsProtocol = location.protocol === 'https' ? 'wss':'ws';
const wsUrl = `${wsProtocol}://${window.location.host}/ws/deliveryman/${deliveryman_id}/`;

const wsHandlers = {};

function connectWS(){
    ws = new WebSocket(wsUrl);

    ws.addEventListener('open',()=>{
        console.log("Connected to Deliveryman WS");
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
    console.log("msgfrombase:",msg);

      if (msg.type === "new_order_available") {
        newDeliveryCount++;
        countElement.innerHTML = newDeliveryCount;
        showNotification();
        document.title = `🔔 New Delivery Request Received`;
        setTimeout(() => { document.title = "Delivery Request"; }, 2000);
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

function resetDeliveryCount() {
    newDeliveryCount = 0;
    countElement.innerHTML = 0;
}

window.resetDeliveryCount = resetDeliveryCount;


function registerWSHandler(name, callback) {
    if(!wsHandlers[name]){
        wsHandlers[name] = callback;
    }
}

window.registerWSHandler = registerWSHandler;
window.addEventListener('DOMContentLoaded', connectWS);

async function fetchInitialDeliverymanState() {
    try {
        const res = await fetch("/json/deliveryman-status-and-orders/", {
            credentials: "include"
        });

        const data = await res.json();

        currentOrderIds = [];

        deliverymanStatus = data.status;
        currentOrderIds = [...data.order_ids];

        console.log("Initial DM state:", {
            deliverymanStatus,
            currentOrderIds
        });

    } catch (err) {
        console.error("Could not fetch initial deliveryman state", err);
    }
}


function startGlobalLocationInterval() {
    if (locationInterval) clearInterval(locationInterval);

    locationInterval = setInterval(() => {
        if (deliverymanStatus !== "OUT_FOR_DELIVERY") return;

        navigator.geolocation.getCurrentPosition((pos) => {
            lastLocation.lat = pos.coords.latitude;
            lastLocation.lng = pos.coords.longitude;
            lastLocation.accuracy = pos.coords.accuracy;

            if (ws && ws.readyState === WebSocket.OPEN) {
                sendWSMessage("deliveryman_location", {
                    order_ids: currentOrderIds,
                    lat: lastLocation.lat,
                    lng: lastLocation.lng,
                    accuracy: lastLocation.accuracy
                });
            }
        });
    }, 5000);
}

async function initialize(){
    await fetchInitialDeliverymanState();
    startGlobalLocationInterval();
}

initialize();

window.updateDeliverymanStatus = (status) => {
    deliverymanStatus = status;  
};

window.updateCurrentOrderIds = (ids) => {
    console.log("Updated order IDs:", ids);
    currentOrderIds = ids;
};


