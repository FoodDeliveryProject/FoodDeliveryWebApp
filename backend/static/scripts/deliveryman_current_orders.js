
document.addEventListener("DOMContentLoaded",()=>{
  let delman_lat;
  let delman_lng;
  let delman_acc;
  let res_lat = 27.7172;
  let res_lng = 85.324 ;
  let assigned_to_res = "Pizza Palace";
  let map = null;
  let layersControl;
  let currentDeliveries = [];
  let isassigned = null;
  let locationInterval = null;
  let deliveryman_status = null;
  let deliveryRoutes = {};
  let deliverymanMarker = null;
  let deliverymanAccCircle = null;

  const deliveryItemContainer = document.querySelector("#delivery-list-container");
  const deliveryInfoContainer = document.querySelector("#delivery-info-container");
  const outForDeliveryBtn = document.querySelector("#out-for-deliverybtn");
  const mapBox = document.querySelector("#map"); 
  const mapErrContainer = document.querySelector("#map-error");


  // function startSendingLocation() {
  //           const currentOrderIds = currentDeliveries.map(d => d.order_id);
  //           console.log("ids:",currentOrderIds)
  //           sendWSMessage("deliveryman_location", {
  //               order_ids: currentOrderIds,
  //               lat: delman_lat,
  //               lng: delman_lng,
  //               accuracy: delman_acc
  //           });

  //          console.log("WS Location Sent:", {
  //               currentOrderIds,
  //               delman_lat,
  //               delman_lng
  //           });
  // }

  function updateDeliveryManLocation(){
    if(!map) return;
    if(!deliverymanMarker && !deliverymanAccCircle) return;
        deliverymanMarker.setLatLng([delman_lat, delman_lng]);
        deliverymanAccCircle.setLatLng([delman_lat, delman_lng]);
        deliverymanAccCircle.setRadius(delman_acc);
  }

  function setLocationInterval(){
    if(locationInterval){
        clearInterval(locationInterval);
      }

     locationInterval = setInterval(() => {
        navigator.geolocation.getCurrentPosition((pos) => {
            const { latitude, longitude, accuracy } = pos.coords;
            delman_lat = latitude;
            delman_lng = longitude;
            delman_acc = accuracy;
            console.log("lat,lng:",delman_lat,delman_lng);
            updateDeliveryManLocation();
            // moved logic to base.js
            // if(deliveryman_status === "OUT_FOR_DELIVERY"){
            //   startSendingLocation();
            // }
        });
    }, 5000); 
}



    async function getCurrentDeliveries() {
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/json/deliveryman-current-delivery/`,
        // `http://192.168.18.53:8000/json/deliveryman-current-delivery/`,
        {
          credentials:"include"
        }
      );
    
      const data = await response.json();
      console.log("data:", data);
      const {has_current_assignments,assigned_restaurant,latitude,longitude,orders,status} = data;
      isassigned = has_current_assignments;
      res_lat = latitude;
      res_lng=longitude;
      assigned_to_res = assigned_restaurant;
      deliveryman_status = status.on_delivery ? "OUT_FOR_DELIVERY":"IDLE";
      if(orders && orders.length>0){
        orders.forEach((item)=> currentDeliveries.push(item));
      }
      const currentOrderIdsLS = orders.map(o => o.order_id);
      window.updateCurrentOrderIds(currentOrderIdsLS);
      window.updateDeliverymanStatus(status.on_delivery ? "OUT_FOR_DELIVERY" : "IDLE");

    } catch (err) {
      console.error("error: ", err);
      showError({ message: `${err?.message}` });
    }
  }

async function initDeliveries() {
    await getCurrentDeliveries();
    renderDeliveries();
}

initDeliveries();


  if(window.registerWSHandler){
    window.registerWSHandler("autoAssignDeliveryHandler" , (msg)=>{
      console.log("msgfromcurrent:",msg);
     if (msg.type === "direct_order_assignment") {
            try{
              currentDeliveries.unshift(...msg.data.orders);
              showError({message:"New Delivery assigned!"},"success");
              renderDeliveries();
            } catch(err){
              console.error("error:",err);
            }
          }
    })
  }


function renderDeliveries(){
    deliveryItemContainer.innerHTML = ""; 
    if(!currentDeliveries.length && map){
      map.remove();
      map = null;
    }
    if(!currentDeliveries.length && !isassigned){
      mapErrContainer.classList.remove("hidden");
      mapErrContainer.style.display = "flex";
      mapBox.style.display = "none";
      deliveryInfoContainer.style.display="none";
       mapErrContainer.innerHTML = `
        <div>
          <p>
            <span><i class="fa-solid fa-triangle-exclamation"></i></span>
            <span>You havenot taken any delivery at the moment.</span> 
          </p>
        </div>
      `;
      return;
    }
    if(deliveryman_status === "OUT_FOR_DELIVERY"){
      outForDeliveryBtn.disabled = true;
      outForDeliveryBtn.style.opacity = "0.5";
      outForDeliveryBtn.style.cursor = "not-allowed";
      // moved logic to base.js
      // startSendingLocation();
    } else{
      outForDeliveryBtn.disabled = false;
      outForDeliveryBtn.style.opacity = "1";
      outForDeliveryBtn.style.cursor = "pointer";
    }
     mapErrContainer.classList.add("hidden");
      mapErrContainer.style.display = "none";
      mapBox.style.display = "inline-block";
      deliveryInfoContainer.style.display = "inline-block";
      deliveryInfoContainer.classList.remove("hidden");

      if(navigator.geolocation){
  navigator.geolocation.getCurrentPosition((pos)=>{
    console.log(pos);
    const {accuracy,latitude,longitude} = pos.coords;
    delman_lat = latitude;
    delman_lng = longitude;
    delman_acc = accuracy;
    initMap();
    setLocationInterval();
  },
  (err)=>{
    console.error("error:",err);
      mapErrContainer.classList.remove("hidden");
      mapErrContainer.style.display = "flex";
      mapBox.style.display = "none";
       let message = "";

      if (err.code === err.PERMISSION_DENIED) {
        message = "Location permission denied. Please allow access to use the map.";
      } else if (err.code === err.POSITION_UNAVAILABLE) {
        message = "Location unavailable. Try again outdoors or check GPS.";
      } else if (err.code === err.TIMEOUT) {
        message = "Location request timed out. Please try again.";
      } else {
        message = "An unknown error occurred while loading the map.";
      }
      mapErrContainer.innerHTML = `
        <div>
          <p>
            <span><i class="fa-solid fa-triangle-exclamation"></i></span>
            <span>${message}</span> 
          </p>
        </div>
      `;
  },
 {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0,
    })
} else {
  mapErrContainer.classList.remove("hidden");
  mapErrContainer.style.display = "flex";
  mapBox.style.display = "none";
  mapErrContainer.innerHTML = `
    <div>
      <p>
        <span><i class="fa-solid fa-triangle-exclamation"></i></span>
        <span>Your device does not support geolocation.</span>
      </p>
    </div>
  `;
}
function initMap(){
   if(map) {
        map.remove(); 
        map = null;
    }

   const osmLight = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 19,
                attribution: "&copy; OpenStreetMap contributors",
              });

  const osmDark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { 
            	attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a hre f="https://carto.com/attributions">CARTO</a>',
            	subdomains: 'abcd', 
            	maxZoom: 20 
            }); 

map = L.map("map",{
  center:[delman_lat,delman_lng],
  zoom:10,
  layers: [osmLight]
})
if(!map) return;
 const baseLayersGrp = {
      "Light mode": osmLight,
      "Dark mode": osmDark
    }
        
  layersControl = L.control.layers(baseLayersGrp);
    layersControl.addTo(map);

    deliverymanMarker = L.marker([delman_lat,delman_lng])
    .bindPopup("Your Location",{ autoClose: true })
    .addTo(map);

    deliverymanAccCircle = L.circle([delman_lat, delman_lng], {
        radius: delman_acc,
        color: "#136AEC",
        fillColor: "#136AEC",
        fillOpacity: 0.15
   }).addTo(map);

   const iconRed = L.icon({
    iconUrl: ICON_RED,
     iconSize: [25, 41],
   });

     L.Routing.control({
            waypoints: [
            L.latLng(delman_lat,delman_lng),
            L.latLng(res_lat,res_lng)
              ],
              show:false,
              createMarker: function(i,waypoint,n){
                let marker;
                if(i===1){
                  marker = L.marker(waypoint.latLng,{icon:iconRed});
                  marker.bindPopup(`${assigned_to_res}`).openPopup();
                }
                return marker;
              }
            }).addTo(map);


//             currentDeliveries.forEach((delivery,index) => {
//                 setTimeout(()=>{
//  L.Routing.control({
//       waypoints: [
//         L.latLng(res_lat, res_lng),
//         L.latLng(parseFloat(delivery.latitude), parseFloat(delivery.longitude)),
//       ],
//       show: false,
//       lineOptions: { styles: [{ color: "green", weight: 3 }] },
//       createMarker: function (i, waypoint) {
//         if (i === 0) return null; 
//         return L.marker(waypoint.latLng,{icon:iconGreen}).bindPopup(`${delivery.user.email}`);
//       },
//     }).addTo(map);
//   },index*2000);
//   });
}

function showDeliveryRoute(delivery) {
   const iconGreen = L.icon({
    iconUrl: ICON_GREEN,
     iconSize: [35, 50],
   });
  if (deliveryRoutes[delivery.order_id]) {
        map.removeControl(deliveryRoutes[delivery.order_id]);
    }

  const routingControl = L.Routing.control({
    waypoints: [
      L.latLng(res_lat, res_lng),       
      L.latLng(parseFloat(delivery.latitude), parseFloat(delivery.longitude))
    ],
    show: false,
    lineOptions: { styles: [{ color: "green", weight: 3 }] },
    createMarker: function(i, waypoint) {
      let marker;
      if (i === 0) return;
      if (i===1){  
        marker = L.marker(waypoint.latLng, {icon: iconGreen}).bindPopup(delivery.user.email);
      }
      return marker;
    }
  }).addTo(map);
  deliveryRoutes[delivery.order_id] = routingControl;
}


currentDeliveries.forEach((delivery, index) => {
  const divBlock = document.createElement('div');
  divBlock.className = 'delivery-card';
  if (!delivery.order_id) {
    console.warn("Skipping delivery with null order_id", delivery);
    return;
}

  divBlock.innerHTML = `
    <div class="delivery-main-detail">
      <h4>Order ID: ${delivery.order_id}</h4>
      <p><span> Customer: </span> ${delivery.user.first_name}</p>
      <p><span> Total: </span> NPR ${delivery.total_price} (excluding delivery charge)</p>
      <p><span> Delivery charge: </span> NPR ${delivery.delivery_charge} (excluding delivery charge)</p>
      <p><span>Status:</span> <strong>${delivery.status}</strong></p>
      <div class="button-container">
      <button class="view-delivery-btn" data-id="${delivery.order_id}">View Delivery</button>
      ${
      delivery.status === 'OUT_FOR_DELIVERY' ? 
      `<button class="delivery-completed-btn" data-id=${delivery.order_id}>Delivery Completed</button> `:
      ""
      }
      </div>
    </div>
    <div class="order-details">
      <div>
        <h4>Order Items:</h4>
        <ul>
          ${delivery.order_items
            .map(
              (item) => `
                <li>
                  <img src="${item.food_item_image}" width="50" height="50" />
                  <span><strong>${item.food_item_name}</strong> (x${item.quantity}) - NPR ${item.total_price}</span>
                </li>`
            )
            .join("")}
        </ul>
      </div>
      <div>
        <h4>Customer Details:</h4>
        <p>Email: ${delivery.user.email}</p>
        <p>Phone: ${delivery.customer_details.phone}</p>
      </div>
      </div>
      <button id="${delivery.order_id}" class="fullpageview-btn"><i class="fa-solid fa-angle-down"></i></button>
  `;

  const btn = divBlock.querySelector(".fullpageview-btn");
  const orderDetails = divBlock.querySelector(".order-details");
  const deliveryCompleted = divBlock.querySelector(".delivery-completed-btn");


  btn.addEventListener("click", () => {
    orderDetails.classList.toggle("show");

    const icon = btn.querySelector("i");
    icon.classList.toggle("rotate");

  });

 divBlock.querySelector('.view-delivery-btn').addEventListener('click', (e) => {
    showDeliveryRoute(delivery);
  });

  // delivery complete vaye paxi ko lagi:
  if(deliveryCompleted){
    deliveryCompleted.addEventListener('click',(e)=>{
    const order_id = delivery.order_id;
    async function deliveryCompletedFunc() {
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/update-order-delivered-status/`,
        // `http://192.168.18.53:8000/api/update-order-delivered-status/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
             "X-CSRFToken": csrftoken
          },
          credentials:"include",
          body: JSON.stringify({order_id:order_id})
        }
      );
      if(response.ok){
        currentDeliveries = currentDeliveries.filter(del => parseInt(del.order_id) !== parseInt(delivery.order_id));
        if (map && deliveryRoutes[order_id]) {
          map.removeControl(deliveryRoutes[order_id]);
          delete deliveryRoutes[order_id];
        }
        showError({message: `successfully delivered ${delivery.order_id}`},"success");
        if(currentDeliveries.length === 0){
          deliveryman_status = "IDLE";
          isassigned = false;
          clearInterval(locationInterval);
          window.updateDeliverymanStatus("IDLE");
          window.updateCurrentOrderIds([]);

          console.log("All orders delivered. Stopped sending live location....");
          showError({message: `successfully delivered all the orders`},"success");
        } else{
          const oids = currentDeliveries.map(ods => ods.order_id);
          window.updateCurrentOrderIds(oids);
        }
        renderDeliveries();
      }
    } catch (err) {
      console.error("error: ", err);
      showError({ message: `${err?.message}` },"error");
    }
    }
    if(window.confirm(`Are you sure delivery of order ${order_id} is completed?`)){
      deliveryCompletedFunc();
    }
    })
  }


  deliveryItemContainer.appendChild(divBlock);
});

  }

  // ya out for delivery click garda ko logic:
  if(outForDeliveryBtn){
    outForDeliveryBtn.addEventListener("click",(e)=>{
      
    async function outForDeliveryRequest() {
    try {
      let payload;
      const order_ids = currentDeliveries.map((del)=> del.order_id);
      if(!order_ids || order_ids.length === 0){
        showError({message:`You don't currently have any delivery!`},"error");
        return;
      }
      console.log("order_ids:",order_ids);
      if(delman_lat && delman_lng){
        const deliveryman_location  = {
          lat: delman_lat,
          lng: delman_lng,
          accuracy: delman_acc
        }
        payload = {
          order_ids,
          deliveryman_location
        }
      }else{
        const deliveryman_location  = {
          lat: "",
          lng: "",
          accuracy: ""
        }
        payload = {
          order_ids,
          deliveryman_location
        }
      }
      const response = await fetch(
        `http://127.0.0.1:8000/api/update-order-out-for-delivery-status/`,
        // `http://192.168.18.53:8000/api/update-order-out-for-delivery-status/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
             "X-CSRFToken": csrftoken
          },
          credentials:"include",
          body: JSON.stringify(payload)
        }
      );
      if(response.ok){
        console.log("Out for delivery successful. Starting live location sending...");
        currentDeliveries.forEach((del)=>{
          del.status = "OUT_FOR_DELIVERY"
        });
        deliveryman_status = "OUT_FOR_DELIVERY";
        renderDeliveries();
        deliveryman_status = "OUT_FOR_DELIVERY";
        window.updateDeliverymanStatus("OUT_FOR_DELIVERY");
        window.updateCurrentOrderIds(order_ids);
        // moves this below logic to base.js
        // startSendingLocation(); 
      }

    } catch (err) {
      console.error("error: ", err);
      showError({ message: `${err?.message}` });
    }
  }
  outForDeliveryRequest();
    })
  }

})