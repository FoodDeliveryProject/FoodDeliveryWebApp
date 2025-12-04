document.addEventListener("DOMContentLoaded", (e) => {
  const summaryCard = document.getElementById("summary2-div");

  summaryCard.addEventListener("mousemove", function (e) {
    const rect = summaryCard.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const rotateX = ((centerY - y) / centerY) * 20;
    const rotateY = ((x - centerX) / centerX) * 20;
    summaryCard.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
  });
  summaryCard.addEventListener("mouseleave", function () {
    summaryCard.style.transform = "rotateX(0deg) rotateY(0deg)";
  });

   const rawData = JSON.parse(document.getElementById("orders-data").textContent);

    const processedData = [...rawData].reverse();

    const weekdayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const today = new Date();

    let labels = [];
    for (let i = 6; i >= 0; i--) {
        let d = new Date();
        d.setDate(today.getDate() - i);
        labels.push(weekdayNames[d.getDay()]);
    }

    const ctx = document.getElementById("ordersChart").getContext("2d");

    new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Orders",
                    data: processedData,
                    borderWidth: 2,
                    borderColor: "#3b2a25",
                    backgroundColor: "#3b2a25",
                    tension: 0.3,
                    pointBackgroundColor: "#3b2a25",
                    pointBorderColor: "#3b2a25",
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#3b2a25",
                    titleColor: "#ffffff",
                    bodyColor: "#ffffff"
                }
            },
            scales: {
                x: {
                    ticks: { color: "#3b2a25", font: { weight: "bold" } },
                    grid: { display: false },
                    border: { color: "#3b2a25" }
                },
                y: {
                    ticks: { color: "#3b2a25", font: { weight: "bold" } },
                    grid: { color: "rgba(0,0,0,0.1)" },
                    border: { color: "#3b2a25" },
                    beginAtZero: true
                }
            }
        }
    });

    const totalOrders = rawData.reduce((a,b) => a+b, 0);
    const averageOrders = (totalOrders / rawData.length).toFixed(2);
    const maxOrders = Math.max(...rawData);
    const minOrders = Math.min(...rawData);
    const ordersToday = rawData[0];
    const zeroDays = rawData.filter(v => v === 0).length;

    const summary2Div = document.querySelector("#summary2-div");
    summary2Div.innerHTML = `
        <h3>Order Statistics</h3>
        <p>Total Orders (7 days): <strong>${totalOrders}</strong></p>
        <p>Average Orders per Day: <strong>${averageOrders}</strong></p>
        <p>Max Orders in a Day: <strong>${maxOrders}</strong></p>
        <p>Min Orders in a Day: <strong>${minOrders}</strong></p>
        <p>Orders Today: <strong>${ordersToday}</strong></p>
        <p>Days with Zero Orders: <strong>${zeroDays}</strong></p>
    `;
});

