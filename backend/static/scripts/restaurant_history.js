
document.addEventListener("DOMContentLoaded", (e) => {
    let orderHistory = [];
    const containerBody = document.querySelector('#container-body');
    const emptyOrder = document.querySelector("#emptyorder");

    async function getOrderHistory(){
        try{
            const response = await fetch("http://127.0.0.1:8000/json/restaurant-order-list/");
            const data = await response.json();
            console.log("orderhistory:",data.data);
            orderHistory = data.data;
        } catch(e){
            console.error("error: ", err);
            showError({ message: `${err?.message}` });
        }
    }

    async function initHistory(){
        await getOrderHistory();
        renderOrders();
    }

    initHistory();

    function renderOrders(){
        containerBody.innerHTML = "";
        if(orderHistory.length === 0){
            emptyOrder.style.display = "flex";
            return;
        }
        emptyOrder.style.display = "none";
        orderHistory.forEach((order)=>{
            const summaryCard = document.createElement("div");
            summaryCard.classList.add("summary-card");
           summaryCard.innerHTML = `
    <div class="main-info">
        <h3> 
            <span><i class="fa-solid fa-tag"></i></span>
            <span>${order.original_order_id ?? order.order_id}</span>
        </h3>
        <i class="fa-solid fa-circle-arrow-right view-details"></i>
        <i class="fa-solid fa-circle-arrow-down view-less hidden"></i>
    </div>

    <div class="openclose">
        <div class="main-body">

            <div class="customer-info">
                <h4>Customer info</h4>
                <p><strong>Customer:</strong> <span>${order.customer_info.customer}</span></p>
                <p><strong>Address:</strong> ${order.customer_info.address}</p>
                <p><strong>Number:</strong> ${order.customer_info.number}</p>
            </div>

            <div class="merchant-info">
                <h4>Merchant info</h4>
                <p><strong>Restaurant Name:</strong> ${order.deliveryman_info.deliveryman_name}</p>
                <p><strong>Address:</strong> ${order.deliveryman_info.phone_number}</p>
                <p><strong>Contact No:</strong> ${order.deliveryman_info.vehicle}</p>
            </div>

            <div class="order-items">
                <h4>Order Items</h4>
                ${order.order_items.map(item => `
                    <p>
                        <strong>${item.item_name}</strong> 
                        (x${item.quantity}) — $${item.price_at_order}
                    </p>
                `).join('')}
            </div>

        </div>
    </div>
`;


        const mainBody = summaryCard.querySelector('.main-body');
        const openClose = summaryCard.querySelector('.openclose');
        const viewMoreBtn = summaryCard.querySelector('.view-details');
        const viewLessBtn = summaryCard.querySelector('.view-less');
        viewLessBtn.classList.add('hidden');
        viewMoreBtn.addEventListener('click', () => {
            mainBody.style.display = "flex";  
            mainBody.style.opacity = 1;  
            openClose.classList.add('open'); 
            viewMoreBtn.classList.add('hidden'); 
            viewLessBtn.classList.remove('hidden'); 
        });
        viewLessBtn.addEventListener('click', () => {
            mainBody.style.display = "none";
            mainBody.style.opacity = 0;
            openClose.classList.remove('open'); 
            viewMoreBtn.classList.remove('hidden');  
            viewLessBtn.classList.add('hidden'); 
        });
       
        containerBody.appendChild(summaryCard);
        })
    }
});
    