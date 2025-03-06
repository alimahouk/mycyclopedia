let didSubmitNewEntry = false;
let newEntryForm = null;
let newEntryProficiencySlider = null;
let exampleForms = null;


document.addEventListener("DOMContentLoaded", function () {
    setUpPage();
});

function handleNewEntryRequest(topic) {
    if (topic.length > 0) {
        const proficiency = newEntryProficiencySlider.value;

        const queryString = `proficiency=${encodeURIComponent(proficiency)}&topic=${encodeURIComponent(topic)}`;
        const url = `/e/new?${queryString}`;
        didSubmitNewEntry = true;
        progressOverlay.classList.remove("hidden");

        fetch(url)
            .then(response => {
                didSubmitNewEntry = false;
                progressOverlay.classList.add("hidden");

                if (response.redirected) {
                    window.location.href = response.url;
                } else {
                    if (response.status == 404) {
                        alert("Unknown topic.");
                    } else if (response.status == 405) {
                        alert("This topic contains or implies content that falls outside acceptable use guidelines.");
                    } else {
                        alert("An error occurred.");
                    }
                }
            })
            .catch(error => {
                didSubmitNewEntry = false;
                progressOverlay.classList.add("hidden");
                alert("An error occurred.");
                console.error("Error:", error);
            });
    }
}

function setUpPage() {
    setUpPageBindings();
    setUpPageEventListeners();
}

function setUpPageBindings() {
    newEntryForm = document.querySelector("#newEntry");
    newEntryProficiencySlider = document.querySelector("#proficiencySlider");
    exampleForms = document.querySelectorAll("#inspiration .example");
}

function setUpPageEventListeners() {
    newEntryForm.addEventListener("submit", function (e) {
        e.preventDefault();
        newEntryForm.topic.blur();
        handleNewEntryRequest(newEntryForm.topic.value);
    });

    for (const exampleForm of exampleForms) {
        exampleForm.addEventListener("submit", function (e) {
            e.preventDefault();
            handleNewEntryRequest(exampleForm.topic.value);
        });
    }
}
