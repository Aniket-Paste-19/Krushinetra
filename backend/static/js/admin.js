async function postJson(url, payload) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify(payload || {})
    });
    return response.json();
}

document.addEventListener("click", async (event) => {
    const editPlantButton = event.target.closest("[data-edit-plant]");
    if (editPlantButton) {
        const plant = JSON.parse(editPlantButton.dataset.editPlant);
        const plantName = window.prompt("पीकाचे नाव", plant.name);
        if (plantName === null) return;
        const description = window.prompt("वर्णन", plant.description || "");
        const response = await fetch(`/admin/update-plant/${plant.id}`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            body: JSON.stringify({ plant_name: plantName, description })
        });
        const payload = await response.json();
        alert(payload.message || payload.error || "पीक अपडेट झाले.");
        if (response.ok) window.location.reload();
    }

    const editDiseaseButton = event.target.closest("[data-edit-disease]");
    if (editDiseaseButton) {
        const disease = JSON.parse(editDiseaseButton.dataset.editDisease);
        const form = document.getElementById("edit-disease-form");
        const modalElement = document.getElementById("editDiseaseModal");
        if (!form || !modalElement) return;

        form.dataset.diseaseId = disease.id;
        form.elements.plant_id.value = String(disease.plant_id);
        form.elements.disease_name.value = disease.name || "";
        form.elements.symptoms.value = disease.symptoms || "";
        form.elements.treatment.value = disease.treatment || "";
        form.elements.supplement.value = disease.supplement || "";
        form.elements.notes.value = disease.notes || "";

        const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        modal.show();
    }

    const deleteButton = event.target.closest("[data-delete-url]");
    if (deleteButton) {
        const confirmed = window.confirm("ही नोंद हटवायची आहे का?");
        if (!confirmed) return;
        const response = await fetch(deleteButton.dataset.deleteUrl, {
            method: "DELETE",
            headers: { "Accept": "application/json" }
        });
        const payload = await response.json();
        alert(payload.message || payload.error || "कृती पूर्ण झाली.");
        if (response.ok) window.location.reload();
    }

    const datasetButton = event.target.closest("[data-generate-dataset]");
    if (datasetButton) {
        const payload = await postJson("/admin/generate-dataset");
        alert(payload.message || payload.error || "डेटासेट प्रक्रिया पूर्ण झाली.");
        if (payload.summary) window.location.reload();
    }

    const syncSeedButton = event.target.closest("[data-sync-seed-dataset]");
    if (syncSeedButton) {
        const payload = await postJson("/admin/sync-seed-dataset");
        alert(payload.message || payload.error || "सीड डेटासेट सिंक पूर्ण झाले.");
        if (payload.result) window.location.reload();
    }

    const trainingButton = event.target.closest("[data-start-training]");
    if (trainingButton) {
        const payload = await postJson("/admin/train-model");
        alert(payload.message || payload.error || "ट्रेनिंग विनंती पूर्ण झाली.");
        startTrainingPoller();
    }
});

document.addEventListener("submit", async (event) => {
    const importForm = event.target.closest("#plantvillage-import-form");
    if (importForm) {
        event.preventDefault();
        const formData = new FormData(importForm);
        const payload = await postJson("/admin/import-plantvillage", {
            source_dir: formData.get("source_dir")
        });
        alert(payload.message || payload.error || "आयात प्रक्रिया पूर्ण झाली.");
        if (payload.result) window.location.reload();
        return;
    }

    const editDiseaseForm = event.target.closest("#edit-disease-form");
    if (!editDiseaseForm) return;

    event.preventDefault();
    const diseaseId = editDiseaseForm.dataset.diseaseId;
    const response = await fetch(`/admin/update-disease/${diseaseId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({
            plant_id: editDiseaseForm.elements.plant_id.value,
            disease_name: editDiseaseForm.elements.disease_name.value,
            symptoms: editDiseaseForm.elements.symptoms.value,
            treatment: editDiseaseForm.elements.treatment.value,
            supplement: editDiseaseForm.elements.supplement.value,
            notes: editDiseaseForm.elements.notes.value
        })
    });
    const payload = await response.json();
    alert(payload.message || payload.error || "रोग अपडेट झाला.");
    if (response.ok) {
        bootstrap.Modal.getInstance(document.getElementById("editDiseaseModal"))?.hide();
        window.location.reload();
    }
});

async function startTrainingPoller() {
    const statusBox = document.getElementById("training-status-box");
    if (!statusBox) return;

    const poll = async () => {
        const response = await fetch("/admin/training-status?format=json", { headers: { "Accept": "application/json" } });
        const payload = await response.json();
        statusBox.textContent = JSON.stringify(payload, null, 2);
        if (payload.status === "training" || payload.status === "preparing") {
            window.setTimeout(poll, 4000);
        }
    };

    poll();
}

window.addEventListener("load", startTrainingPoller);
