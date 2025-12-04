
document.addEventListener("DOMContentLoaded", () => {
  const orderWrapper = document.querySelector("#current-order-wrapper");
  const statusFilter = document.getElementById("order_status_select");
  const emptyOrder = document.querySelector("#emptyorder");
  const loadMoreBtn = document.querySelector("#loadmore");
  const resid = document.querySelector(".resid").id;
  let orders = [];
  const orderMaps = {};  
  const orderRoutes = {};
  const limitIncSize = 10;
  let lastLimitId = null;
  let orderStatus = 'ALL';
  let loadMoreFinished = null;


function updateDeliverymanMarker(order_id) {
  const mapObj = orderMaps[order_id];
  if (!mapObj || !mapObj.map) return;

  const order = orders.find(
    (od) => parseInt(od.order_id) === parseInt(order_id)
  );
  if (!order || !order.deliverymanLocation) return;

  const { lat, lng } = order.deliverymanLocation;


  if (!mapObj.deliverymanMarker) {
    mapObj.deliverymanMarker = L.marker([lat, lng])
      .addTo(mapObj.map)
      .bindPopup("Deliveryman");
    updateRoutingPath(order_id);
  } else {
    mapObj.deliverymanMarker.setLatLng([lat, lng]);
  }
}

function updateRoutingPath(order_id) {
  const mapObj = orderMaps[order_id];
  if (!mapObj || !mapObj.map) return;

  const order = orders.find(
    (od) => parseInt(od.order_id) === parseInt(order_id)
  );
  if (!order || !order.deliverymanLocation) return;

  const deliveryman = order.deliverymanLocation;
  const customer = {
    lat: order.latitude,
    lng: order.longitude,
  };

  if (orderRoutes[order_id]) {
    mapObj.map.removeControl(orderRoutes[order_id]);
  }

  const routeControl = L.Routing.control({
    waypoints: [
      L.latLng(deliveryman.lat, deliveryman.lng),
      L.latLng(customer.lat, customer.lng)
    ],
    lineOptions: {
      styles: [{ color: "red", weight: 5 }]
    },
    createMarker: function() {
      return null;
    },
    addWaypoints: false,
    draggableWaypoints: false,
    fitSelectedRoutes: true,
    show: false
  }).addTo(mapObj.map);

  orderRoutes[order_id] = routeControl;
}


statusFilter.addEventListener("change", async () => {
  const status = statusFilter.value;
  orderStatus = status;
  lastLimitId = null;
  orders = []; 
  await getCurrentOrders();
  renderOrders();            
});

loadMoreBtn.addEventListener("click", async ()=>{
  const lastorderId = orders[orders.length-1].order_id;
  if(lastorderId){
    lastLimitId = lastorderId;
    await getCurrentOrders();
    renderOrders();
  }

})



async function getCurrentOrders() {
  try {
    let url = `http://127.0.0.1:8000/json/restaurant-orders-response/${resid}`;
    const isFiltering = orderStatus && orderStatus !== "ALL";
    const hasLastId = Boolean(lastLimitId);
    if (isFiltering) {
      url += `?status=${orderStatus}`;
    } else{
      url += `?`;
    }

    if(hasLastId){
      url += `&limit=${limitIncSize}&last_limit_id=${lastLimitId}`;
    } else {
      url += `&limit=${limitIncSize}`;
    }
    const response = await fetch(url);
    const  {data,finished} = await response.json();
    loadMoreFinished = finished;

    if (hasLastId) {
      orders = [...orders, ...data];
    } 
    else {
      orders = data;
    }
    console.log("neworders:",orders)
  } catch (err) {
    console.error("error: ", err);
    showError({ message: `${err?.message}` });
  }
}


  async function initOrders(){
    await getCurrentOrders();
    renderOrders();
  }

  initOrders();

    if (window.registerWSHandler) {
      window.registerWSHandler("orderPageHandler", (msg) => {

          if (msg.type === "chat") {
            try{
              setTimeout(() => {
              if (window.resetOrderCount) {
              window.resetOrderCount();
            }
          }, 1000);
            const filteredData = msg.data.filter(
              (order) =>
              statusFilter.value === "ALL" ||
              order.status === statusFilter.value
             );
            if (filteredData.length) {
              orders.unshift(...filteredData);
              orderWrapper.innerHTML = "";
              renderOrders();
            }
          } catch(err){
              console.error("error:",err);
            }
          }
      });

      window.registerWSHandler("deliverymanLocationHandler", (msg) => {
       if (msg.type === "deliveryman_location") {
        const {order_id,lat,lng,accuracy} = msg;
        if(!order_id || !lat || !lng || !accuracy){
          return;
        }
        console.log("WSMSG:",msg);
        const order_data = orders.find(od => parseInt(od.order_id) === parseInt(order_id))
        if (!order_data) return;

        order_data.deliverymanLocation = { lat, lng, accuracy };
        updateDeliverymanMarker(order_id);
      }
    });

  } else {
      console.error("WebSocket not initialized yet");
  }

  function renderOrders() {
    orderWrapper.innerHTML = "";
    console.log(orders.length);
    if (orders.length === 0) {
      emptyOrder.style.display = "flex";
      loadMoreBtn.style.display = "none";
      return;
    }
    emptyOrder.style.display = "none";
    if(loadMoreFinished){
      loadMoreBtn.style.display = "none";
    } else{
      loadMoreBtn.style.display = "inline-block";
    }
    orders.forEach((order) => {
      const orderCard = document.createElement("div");
      orderCard.classList.add("order-card");

      const showRequestDeliveryBtn =
        order.status === "PROCESSING" && !order.deliveryman;

      const mapDivId = `userlocmap-${order.order_id}`;

      orderCard.innerHTML = `
          <div class="order-summary">
            <div>
              <h4>Order ID: ${order.order_id}</h4>
              <p>Customer: ${order.user.first_name}</p>
              <p>Total: NPR ${order.total_price}</p>
              <p>Status: <strong>${order.status}</strong></p>
            </div>
            <div>
              <button class="toggle-details">Details</button>
              ${
                order.status === "PENDING" 
                  ? '<button class="next-status">Next Status</button>'
                  : ""
              }
              ${
                showRequestDeliveryBtn
                  ? '<button class="request-delivery">Request Delivery</button>' 
                  : ""
              }
            </div>
          </div>
         <div class="order-details">
          <div>
          <div>
          <h4>Order Items:</h4>
            <ul>
              ${order.order_items
                .map(
                  (item) => `
                <li>
                  <img src="${item.food_item_image}" width="50" height="50" />
                  <span>${item.food_item_name} (x${item.quantity}) - NPR ${item.total_price}</span>
                </li>`
                )
                .join("")}
            </ul>
            </div>
            <div>
            <h4>Customer Details:</h4>
            <p>Email: ${order.user.email}</p>
            <p>Phone: ${order.customer_details.phone}</p></div>
            </div>
            <div><h4>Delivery Location: (${order.latitude}, ${order.longitude})</h4>
            <div id="${mapDivId}" style="height: 400px; width:70dvw;"></div>
            </div>
          </div>
        `;

      // Toggle details
       orderCard
        .querySelector(".toggle-details")
        .addEventListener("click", () => {
          const detailBox = orderCard.querySelector(".order-details");
          if (!detailBox.style.display || detailBox.style.display === "none") {
            detailBox.style.display = "flex";

            if (!detailBox.dataset.mapInitialized) {
              const map = L.map(mapDivId, {
                boxZoom: false,
                keyboard: false,
                tap: false,
              }).setView([order.latitude, order.longitude], 15);
              orderMaps[order.order_id] = {
                map,
                deliverymanMarker: null
              };
              L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 19,
                attribution: "&copy; OpenStreetMap contributors",
              }).addTo(map);

              L.marker([order.latitude, order.longitude], { draggable: false })
                .addTo(map)
                .bindPopup("Customer Location")
                .openPopup();

              detailBox.dataset.mapInitialized = true;
            }
          } else {
            detailBox.style.display = "none";
          }
        });

      // Update status (merchant allowed only up to Waiting for Delivery)
      const statusBtn = orderCard.querySelector(".next-status");
      if (statusBtn) {
        statusBtn.addEventListener("click", async () => {
          const allowedStatuses = [
            "PENDING",
            "PROCESSING",
          ];
          const nextStatus =
            allowedStatuses[allowedStatuses.indexOf(order.status) + 1];
          if (nextStatus) {
            try{
               const res = await fetch(
              `http://127.0.0.1:8000/api/update-order-status/`,
              {
                method: "POST",
                headers: { "Content-Type": "application/json","X-CSRFToken": csrftoken },
                body: JSON.stringify({ status: nextStatus, order_id: order.order_id }),
                credentials: "include"
              }
            );
            if (res.ok) {
              order.status = nextStatus;
              renderOrders();
            }
            } catch(err){
              console.error("error when updating status in server");
            }
          }
        });
      }

      // Request Delivery (will forward to all deliverymen)
      const reqBtn = orderCard.querySelector(".request-delivery");
      if (reqBtn) {
        reqBtn.addEventListener("click", async () => {
          if(window.confirm("Do you want to send request for deliveryman?")){
                try{
             const res = await fetch(
            `http://127.0.0.1:8000/api/set-waiting-for-delivery/`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json","X-CSRFToken": csrftoken },
              body: JSON.stringify({ order_id: order.order_id }),
              credentials: "include"
            }
          );
          if (res.ok) {
            order.status = "WAITING_FOR_DELIVERY";
            alert("Delivery request sent. Awaiting acceptance...");
            renderOrders();
          }
          } catch(err){
            console.error("error when requesting for deliveryman");
          } 
          } else{
            return;
          }
        });
      }

      orderWrapper.appendChild(orderCard);
    });
  }
});
