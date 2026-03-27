function buildChart(elementId, type, labels, values, label, color) {
    const element = document.getElementById(elementId);
    if (!element) return;
    new Chart(element, {
        type,
        data: {
            labels,
            datasets: [{
                label,
                data: values,
                backgroundColor: color,
                borderColor: color,
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

window.addEventListener("load", () => {
    const payloadNode = document.getElementById("statistics-payload");
    if (!payloadNode) return;

    const payload = JSON.parse(payloadNode.textContent);
    buildChart(
        "diseaseFrequencyChart",
        "line",
        payload.disease_frequency.map(item => item.label),
        payload.disease_frequency.map(item => item.total),
        "तपासण्या",
        "#198754"
    );
    buildChart(
        "plantUsageChart",
        "bar",
        payload.plant_usage.map(item => item.label),
        payload.plant_usage.map(item => item.total),
        "शोध",
        "#0d6efd"
    );
    buildChart(
        "modelUsageChart",
        "doughnut",
        payload.model_usage.map(item => item.label),
        payload.model_usage.map(item => item.total),
        "तपासण्या",
        ["#198754", "#0d6efd", "#ffc107", "#dc3545", "#6f42c1"]
    );
    buildChart(
        "topFarmersChart",
        "bar",
        payload.top_farmers.map(item => item.label),
        payload.top_farmers.map(item => item.total),
        "शोध",
        "#fd7e14"
    );
});
