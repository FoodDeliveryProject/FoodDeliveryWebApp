
document.addEventListener('DOMContentLoaded',()=>{
   const orderWrapper = document.querySelector("#current-order-list");
   const notice = document.querySelector("#currently-assigned-notice");
  const emptyOrder = document.querySelector("#emptyorder");
  let newDeliveryRequest= [];
  let deliverymanPosition = null;
  let assigned;

navigator.geolocation.getCurrentPosition(
  pos => {
    deliverymanPosition = {
      lat: pos.coords.latitude,
      lng: pos.coords.longitude,
    };
  },
  err => console.warn("Could not get deliveryman location:", err)
);


  async function getCurrentOrders() {
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/json/deliveryman-delivery-requests/`,
        // `http://192.168.18.53:8000/json/deliveryman-delivery-requests/`,
        {
          credentials:"include"
        }
      );
    
      const data = await response.json();
      const {assigned_to_me,orders} = data;
      console.log("data:", assigned_to_me);
      console.log("response:", data);
      assigned = assigned_to_me;
      newDeliveryRequest = [];
      if(orders && orders.length>0){
        orders.forEach((item)=> newDeliveryRequest.push(item));
      }
    } catch (err) {
      console.error("error: ", err);
      showError({ message: `${err?.message}` });
    }
  }

  async function initDeliveryRequest(){
    await getCurrentOrders();
    renderOrders();
  }

  initDeliveryRequest();

  if(window.registerWSHandler){
    window.registerWSHandler("deliveryRequestHandler" , (msg)=>{
      console.log("msg:",msg);
     if (msg.type === "new_order_available") {
            try{
              setTimeout(() => {
              if (window.resetDeliveryCount) {
              window.resetDeliveryCount();
            }
          }, 1000);
              newDeliveryRequest.unshift(...msg.data.orders);
              renderOrders();
            } catch(err){
              console.error("error:",err);
            }
          }

    })
  }

  function renderOrders() {
    console.log("datadata:",newDeliveryRequest);
    orderWrapper.innerHTML = "";
    console.log("len:",newDeliveryRequest.length);
     if(assigned){
      orderWrapper.style.height = "60vh";
      orderWrapper.style.overflow = "hidden";
      notice.classList.remove("hidden");
    } else{
      orderWrapper.style.height = "auto";
      orderWrapper.style.overflow = "auto";
      notice.classList.add("hidden");
    }

      if (newDeliveryRequest.length === 0) {
      console.log("emptyOrder =", emptyOrder);
      emptyOrder.style.display = "flex";
      return;
    } 
   
    emptyOrder.style.display = "none";


    console.log("deliveriesreq:",newDeliveryRequest);
    newDeliveryRequest.forEach((order) => {
      const orderCard = document.createElement("div");
      orderCard.classList.add("order-card");

      const showRequestDeliveryBtn =
        order.status === "WAITING_FOR_DELIVERY" && !order.deliveryman;

      const mapDivId = `userlocmap-${order.order_id}`;

      orderCard.innerHTML = `
          <div class="order-summary">
            <div>
              <h4>Order ID: ${order.order_id}</h4>
              <p>Customer: ${order.user.first_name}</p>
              <p>Total: NPR ${order.total_price}(excluding delivery charge)</p>
              <p>Delivery charge: NPR ${order.delivery_charge}(excluding delivery charge)</p>
              <p>Status: <strong>${order.status}</strong></p>
            </div>
            <div>
              <button class="toggle-details">Details</button>
              ${
                (order.status === "WAITING_FOR_DELIVERY" && !assigned)
                  ? '<button class="accept_request">Accept Request</button>'
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
            // detailBox.style.flexDirection= "column";

            const customerLat = parseFloat(order.latitude);
            const customerLng = parseFloat(order.longitude);

            const restaurantLat = parseFloat(order.restaurant.latitude);
            const restaurantLng = parseFloat(order.restaurant.longitude);

            const deliverymanLat = deliverymanPosition?.lat ?? null;
            const deliverymanLng = deliverymanPosition?.lng ?? null;

            if (!detailBox.dataset.mapInitialized) {
              
              const osmLight = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 19,
                attribution: "&copy; OpenStreetMap contributors",
              });

              const osmDark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { 
            	attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a hre f="https://carto.com/attributions">CARTO</a>',
            	subdomains: 'abcd', 
            	maxZoom: 20 
            }); 
              
              const map = L.map(mapDivId,{
                center: [customerLat, customerLng], 
                zoom: 15,
                layers:[osmLight],
              });

              const baseLayersGrp = {
                "Light mode": osmLight,
                "Dark mode": osmDark
              }
        
              const layersControl = L.control.layers(baseLayersGrp);
              layersControl.addTo(map);

            // Deliveryman Marker
            if (deliverymanLat && deliverymanLng) {
              const deliverymanMarker = L.marker([deliverymanLat, deliverymanLng], { draggable: false});
              deliverymanMarker.bindPopup(`Your location: ${deliverymanMarker.getLatLng()}`);
              layersControl.addOverlay(deliverymanMarker,"Your Location");
            }

            L.Routing.control({
            waypoints: [
            L.latLng(restaurantLat,restaurantLng),
            L.latLng(customerLat,customerLng)
              ],
              createMarker: function(i,waypoint,n){
                const marker = L.marker(waypoint.latLng);
                if(i===0){
                  marker.bindPopup(order.restaurant.restaurant_name ?? "Restaurant Location").openPopup();
                } else if(i===1){
                  marker.bindPopup("Customer Location").openPopup();
                }
                return marker;
              }
            }).addTo(map);
        
              detailBox.dataset.mapInitialized = true;
            }
          } else {
            detailBox.style.display = "none";
          }
        });

      // Update status (merchant allowed only up to Waiting for Delivery)
      const statusBtn = orderCard.querySelector(".accept_request");
      if (statusBtn) {
        statusBtn.addEventListener("click", async () => {
         const resId = order.restaurant_id;
          if (window.confirm("Do you want to accept the order?")) {
            try{
               const res = await fetch(
              `http://127.0.0.1:8000/api/deliveryman-accept-order/`,
              // `http://192.168.18.53:8000/api/deliveryman-accept-order/`,
              {
                method: "POST",
                headers: { "Content-Type": "application/json","X-CSRFToken": csrftoken },
                body: JSON.stringify({ order_id: order.order_id }),
                credentials: "include"
              }
            );
            if (res.ok) {
              // order.status = "";
              assigned = true;
              orderWrapper.innerHTML = "";
              newDeliveryRequest = newDeliveryRequest.filter(del => parseInt(del.restaurant_id) !== parseInt(resId) );
              renderOrders();
            }
            } catch(err){
              console.error("error when updating status in server");
            }
          }
        });
      }

      orderWrapper.appendChild(orderCard);
    });
  }


})