let accuracyNotice = null;
let askAssistantButton = null;
let assistantInputForm = null;
let assistantInputTextarea = null;
let chatContext = null;
let chatContextSectionID = null;
let chatWindow = null;
let chatWindowCloseButton = null;
let chatWindowContextLabel = null;
let chatWindowMessageList = null;
let content = null;
let coverImage = null;
let coverImageProgressIndicator = null;
let coverImageSourceLabel = null;
let didGetCoverImage = false;
let didSubmitChat = false;
let didSubmitNewEntry = false;
let entryProgressIndicator;
let isLoadingSection = false;
let isNew = null;
let lookUpButton = null;
let newEntryForm = null;
let progressOverlay = null;
let relatedTopics = null;
let relatedTopicsContainer = null;
let resetChat = 0;
let selectedText = null;
let selectionPopup = null;
let shouldDisplaySelectionPopup = false;
let toc = null;

const Enum = (arr) => Object.freeze(arr.reduce((acc, key, i) => ({ ...acc, [key]: i }), {}));
const ALLOWED_POPUP_ACTIONS = Enum([
    "ASK_ASSISTANT",
    "LOOK_UP"
]);


document.addEventListener("DOMContentLoaded", function () {
    setUpPage();
});

function activatePage(index) {
    // Reset page visibility.
    const pages = document.querySelectorAll("article .content .page");
    pages.forEach(page => {
        page.classList.add("hidden");
    });

    // Activate the ToC item.
    const tocItems = document.querySelectorAll("#toc>li");
    if (tocItems != null && tocItems.length > 0) {
        tocItems.forEach(item => {
            item.classList.remove("active");
        });
        tocItems[index].classList.add("active");
    }

    if (pages.length == 0) {
        getSections();
    } else if (index < pages.length) {
        const page = pages[index];
        const firstSection = page.querySelector("section");
        const firstSectionContent = firstSection.querySelector(".sectionContent");

        if (firstSectionContent == null || firstSectionContent.innerHTML.trim() == "") {
            accuracyNotice.classList.add("hidden");
            relatedTopicsContainer.classList.add("hidden");
            entryProgressIndicator.classList.remove("hidden");

            getSection(firstSection.id);
        } else {
            accuracyNotice.classList.remove("hidden");
            entryProgressIndicator.classList.add("hidden");

            pages[index].classList.remove("hidden");

            if (entryHasRelatedTopics()) {
                relatedTopicsContainer.classList.remove("hidden");
            }
        }
    }
}

function calculateGlobalOffset(root, range) {
    let totalOffset = 0;
    const iterateNodes = function (node) {
        if (!node) {
            return true; // Continue if the node is null or undefined
        }
        if (node === range.startContainer) {
            return false;
        }
        if (node.nodeType === Node.TEXT_NODE) {
            totalOffset += node.length;
        }
        for (let child of node.childNodes) {
            if (!iterateNodes(child)) {
                return false;
            }
        }
        return true;
    };

    iterateNodes(root);

    return totalOffset + range.startOffset;
}

function dismissChatWindow() {
    chatWindow.classList.add("hidden");
    assistantInputTextarea.value = "";
    chatWindowContextLabel.innerHTML = "";
    chatContextSectionID = null;

    var messages = chatWindowMessageList.querySelectorAll(".chatMessage");
    // Convert HTMLCollection to Array to avoid live collection issues.
    var messagesArray = Array.from(messages);
    messagesArray.forEach(function (message) {
        chatWindowMessageList.removeChild(message);
    });
}

function dismissSelectionPopup() {
    selectionPopup.classList.add("hidden");
}

function entryHasRelatedTopics() {
    return (relatedTopics.innerHTML.trim() != "");
}

function getChatCompletion() {
    if (!didSubmitChat) {
        let userQuery = assistantInputTextarea.value.trim();

        if (userQuery.length > 0) {
            assistantInputForm.classList.add("loading");
            assistantInputTextarea.value = "";
            didSubmitChat = true;

            const userChatMessage = document.createElement("li");
            userChatMessage.className = "chatMessage";
            userChatMessage.classList.add("user");

            const userChatMessageTitle = document.createElement("h5");
            userChatMessageTitle.className = "sender";
            userChatMessageTitle.innerHTML = "You";
            userChatMessage.appendChild(userChatMessageTitle);

            const userChatMessageContent = document.createElement("div");
            userChatMessageContent.className = "content";
            userChatMessageContent.innerHTML = marked.parse(userQuery);
            userChatMessage.appendChild(userChatMessageContent);

            chatWindowMessageList.appendChild(userChatMessage);
            chatWindowMessageList.scrollTo(0, chatWindowMessageList.scrollHeight); // Scroll to bottom.

            const entryID = document.querySelector("article").getAttribute("id");
            const eventSource = new EventSource(`/e/${entryID}/chat/make?context=${encodeURIComponent(chatContext)}&query=${encodeURIComponent(userQuery)}&reset=${encodeURIComponent(resetChat)}&section_id=${encodeURIComponent(chatContextSectionID)}`);
            resetChat = 0;

            eventSource.onmessage = function (event) {
                if (event.data === "event: close") {
                    assistantInputForm.classList.remove("loading");
                    didSubmitChat = false;

                    eventSource.close();
                } else {
                    const response = event.data;

                    const assistantChatMessage = document.createElement("li");
                    assistantChatMessage.className = "chatMessage";
                    assistantChatMessage.classList.add("assistant");

                    const assistantChatMessageTitle = document.createElement("h5");
                    assistantChatMessageTitle.className = "sender";
                    assistantChatMessageTitle.innerHTML = "Assistant";
                    assistantChatMessage.appendChild(assistantChatMessageTitle);

                    const assistantChatMessageContent = document.createElement("div");
                    assistantChatMessageContent.className = "content";
                    assistantChatMessageContent.innerHTML = marked.parse(response);
                    assistantChatMessage.appendChild(assistantChatMessageContent);

                    chatWindowMessageList.appendChild(assistantChatMessage);
                    chatWindowMessageList.scrollTo(0, chatWindowMessageList.scrollHeight); // Scroll to bottom.
                }
            };

            eventSource.onerror = function (error) {
                assistantInputForm.classList.remove("loading");
                didSubmitChat = false;

                console.error("EventSource failed:", error);
                eventSource.close();
            };


        }
    }
}

async function getCoverImage() {
    const entryID = document.querySelector("article").getAttribute("id");
    const eventSource = new EventSource(`/e/${entryID}/image/get-cover`);

    coverImage.classList.remove("hidden");

    eventSource.onmessage = function (event) {
        if (event.data === "event: close") {
            coverImageProgressIndicator.classList.add("hidden");

            if (!didGetCoverImage) { // Failed to get image.
                coverImage.classList.add("hidden");
            }

            eventSource.close();
        } else {
            const jsonObject = JSON.parse(event.data);

            if (!jsonObject.hasOwnProperty("error")) {
                if (jsonObject.url != null) {
                    const imageSource = jsonObject.source;
                    const imageURL = jsonObject.url;

                    coverImage.href = imageURL;
                    coverImage.style.backgroundImage = `url('${imageURL}')`;

                    if (imageSource != null) {
                        coverImageSourceLabel.innerHTML = `Source: ${imageSource}`;
                        coverImageSourceLabel.classList.remove("hidden");
                    } else {
                        coverImageSourceLabel.classList.add("hidden");
                    }

                    coverImageProgressIndicator.classList.add("hidden");

                    didGetCoverImage = true;
                }
            }
        }
    };

    eventSource.onerror = function (error) {
        coverImageProgressIndicator.classList.add("hidden");

        if (!didGetCoverImage) { // Failed to get image.
            coverImage.classList.add("hidden");
        }

        console.error("EventSource failed:", error);
        eventSource.close();
    };
}

async function getRelatedTopics() {
    const entryID = document.querySelector("article").getAttribute("id");
    const eventSource = new EventSource(`/e/${entryID}/get-related-topics`);

    eventSource.onmessage = function (event) {
        if (event.data === "event: close") {
            accuracyNotice.classList.remove("hidden");
            entryProgressIndicator.classList.add("hidden");
            eventSource.close();
        } else {
            const jsonObject = JSON.parse(event.data);

            if (!jsonObject.hasOwnProperty("error")) {
                const queryString = `topic=${encodeURIComponent(jsonObject.topic)}`;
                const url = `/e/new?${queryString}`;

                relatedTopicsContainer.classList.remove("hidden");

                const topicContainer = document.createElement("li");

                const topic = document.createElement("a");
                topic.className = "topic";
                topic.href = url;
                topic.id = jsonObject.id;
                topic.innerHTML = jsonObject.topic;
                topicContainer.appendChild(topic);

                topic.addEventListener("click", function (e) {
                    e.preventDefault();
                    handleRelatedTopicLinkClick(this);
                });

                relatedTopics.appendChild(topicContainer);
            } else {
                const error = jsonObject.hasOwnProperty("error");
                console.error(error.error_message);
            }
        }
    };

    eventSource.onerror = function (error) {
        accuracyNotice.classList.remove("hidden");
        entryProgressIndicator.classList.add("hidden");

        console.error("EventSource failed:", error);
        eventSource.close();
    };
}

function getSection(sectionID) {
    if (!isLoadingSection) {
        isLoadingSection = true;
        toc.classList.add("loading");

        const entryID = document.querySelector("article").getAttribute("id");
        const eventSource = new EventSource(`/e/${entryID}/section/${sectionID}/make`);
        const pages = document.querySelectorAll("article .content .page");

        eventSource.onmessage = function (event) {
            if (event.data === "event: close") {
                insertFunFacts();

                accuracyNotice.classList.remove("hidden");
                entryProgressIndicator.classList.add("hidden");
                toc.classList.remove("loading");

                if (entryHasRelatedTopics()) {
                    relatedTopicsContainer.classList.remove("hidden");
                }

                isLoadingSection = false;
                eventSource.close();
            } else {
                const jsonObject = JSON.parse(event.data);

                if (!jsonObject.hasOwnProperty("error")) {
                    const isSubsection = (jsonObject.parent_id != null);
                    let page;

                    if (!isSubsection) {
                        page = pages[jsonObject.index];
                        page.innerHTML = "";
                        page.classList.remove("hidden"); // Unhide to allow the user to see content as it loads.
                    } else {
                        parent = document.getElementById(jsonObject.parent_id);
                        page = parent.closest(".page");
                    }

                    const section = document.createElement("section");
                    section.id = jsonObject.id;
                    section.setAttribute("data-section-id", `s-${jsonObject.id}`);

                    if (isSubsection) {
                        section.className = "sub";
                    } else {
                        section.className = "super";
                    }

                    const sectionTitle = document.createElement("h2");
                    sectionTitle.className = "sectionTitle";
                    sectionTitle.innerHTML = jsonObject.title;
                    section.appendChild(sectionTitle);

                    const sectionContent = document.createElement("div");
                    sectionContent.className = "sectionContent";
                    sectionContent.innerHTML = jsonObject.content_html;
                    section.appendChild(sectionContent);
                    page.appendChild(section);
                } else {
                    const error = jsonObject.hasOwnProperty("error");
                    console.error(error.error_message);
                }
            }
        };

        eventSource.onerror = function (error) {
            insertFunFacts();

            accuracyNotice.classList.remove("hidden");
            entryProgressIndicator.classList.add("hidden");
            toc.classList.remove("loading");

            if (entryHasRelatedTopics()) {
                relatedTopicsContainer.classList.remove("hidden");
            }

            isLoadingSection = false;
            console.error("EventSource failed:", error);
            eventSource.close();
        };
    }
}

function getSections() {
    const entryID = document.querySelector("article").getAttribute("id");
    const eventSource = new EventSource(`/e/${entryID}/section/make`);
    let sections = Array();

    eventSource.onmessage = function (event) {
        if (event.data === "event: close") {
            if (isNew) {
                makeTOC(sections);
                getRelatedTopics();
            } else {
                accuracyNotice.classList.remove("hidden");
                entryProgressIndicator.classList.add("hidden");

                if (entryHasRelatedTopics()) {
                    relatedTopicsContainer.classList.remove("hidden");
                }
            }

            insertFunFacts();
            eventSource.close();
        } else {
            const jsonObject = JSON.parse(event.data);

            if (!jsonObject.hasOwnProperty("error")) {
                if (isNew == null) {
                    content.innerHTML = ""; // Fresh entry.
                    toc.innerHTML = "";
                    accuracyNotice.classList.add("hidden");
                    relatedTopicsContainer.classList.add("hidden");
                    entryProgressIndicator.classList.remove("hidden");

                    getCoverImage();

                    isNew = true;
                }
            } else {
                accuracyNotice.classList.remove("hidden");
                entryProgressIndicator.classList.add("hidden");

                isNew = false;

                if (entryHasRelatedTopics()) {
                    const relatedTopics = document.querySelectorAll("#relatedTopics .topic");
                    relatedTopics.forEach(topic => {
                        topic.addEventListener("click", function (e) {
                            e.preventDefault();
                            handleRelatedTopicLinkClick(this);
                        });
                    });

                    relatedTopicsContainer.classList.remove("hidden");
                }
            }

            if (isNew) {
                const isSubsection = (jsonObject.parent_id != null);
                let page;

                if (!isSubsection) {
                    page = document.createElement("div");
                    page.className = "page";
                    content.appendChild(page);

                    if (sections.length > 0) {
                        page.classList.add("hidden");
                    }

                    sections.push(jsonObject);
                } else {
                    for (let section of sections) {
                        if (section.id == jsonObject.parent_id) {
                            if (section.subsections != null) {
                                section.subsections.push(jsonObject);
                            } else {
                                section.subsections = [jsonObject];
                            }

                            break;
                        }
                    }

                    parent = document.getElementById(jsonObject.parent_id);
                    page = parent.closest(".page");
                }

                const section = document.createElement("section");
                section.id = jsonObject.id;
                section.setAttribute("data-section-id", `s-${jsonObject.id}`);
                page.appendChild(section);

                if (isSubsection) {
                    section.className = "sub";
                } else {
                    section.className = "super";
                }

                const sectionTitle = document.createElement("h2");
                sectionTitle.className = "sectionTitle";
                sectionTitle.innerHTML = jsonObject.title;
                section.appendChild(sectionTitle);

                const sectionContent = document.createElement("div");
                sectionContent.className = "sectionContent";
                section.appendChild(sectionContent);

                if (jsonObject.content_html != null) {
                    sectionContent.innerHTML = jsonObject.content_html;
                }
            }
        }
    };

    eventSource.onerror = function (error) {
        if (isNew) {
            makeTOC(sections);
            getRelatedTopics();
        } else {
            accuracyNotice.classList.remove("hidden");
            entryProgressIndicator.classList.add("hidden");

            if (entryHasRelatedTopics()) {
                relatedTopicsContainer.classList.remove("hidden");
            }
        }

        insertFunFacts();

        console.error("EventSource failed:", error);
        eventSource.close();
    };
}

function handleNewEntryRequest(topic) {
    if (topic != null && topic.length > 0) {
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

function handleRelatedTopicLinkClick(linkElement) {
    if (linkElement != null && linkElement.innerHTML.length > 0) {
        const topic = linkElement.innerHTML;
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

function handleTextSelection() {
    const selection = window.getSelection();
    const selectionText = selection.toString().trim();
    let didSelectActionableElement = false;

    if (selectionText.length > 0) {
        selectedText = selection.toString().trim();
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        const commonAncestor = range.commonAncestorContainer;

        let currentElement = commonAncestor.nodeType === 3 ? commonAncestor.parentNode : commonAncestor;
        if (currentElement.id === "summary") {
            // Traverse up the DOM tree to check if this is the summary in the header.
            let parent = currentElement.parentNode;
            while (parent) {
                if (parent.tagName === "HEADER") {
                    presentSelectionPopup(null, rect, [ALLOWED_POPUP_ACTIONS.LOOK_UP]);
                    didSelectActionableElement = true;
                    break;
                }
                parent = parent.parentNode;
            }
        }

        if (!didSelectActionableElement) {
            while (currentElement != null) {
                let ancestor = currentElement.closest("div.content");
                if (ancestor) {
                    let section = currentElement.closest("section");
                    if (!section) {
                        section = currentElement.closest("div.funFact");
                    }

                    didSelectActionableElement = true;
                    const sectionID = section.id;
                    presentSelectionPopup(sectionID, rect, [ALLOWED_POPUP_ACTIONS.ASK_ASSISTANT, ALLOWED_POPUP_ACTIONS.LOOK_UP]);
                    break;
                }
                currentElement = currentElement.parentElement;
            }
        }
    }
}

function handleTOCLinkClick(linkElement) {
    // Highlight the clicked ToC item.
    var currentElement = linkElement;
    const isSubsection = linkElement.classList.contains("subsection");
    const sectionID = linkElement.getAttribute("data-section-id");

    while (currentElement && currentElement.parentElement) {
        if (currentElement.tagName === 'LI' && currentElement.parentElement.id === 'toc') {
            break;
        }
        currentElement = currentElement.parentElement;
    }

    var sectionIndex = -1;
    if (currentElement && currentElement.tagName === 'LI') {
        var tocChildren = Array.from(currentElement.parentElement.children);
        sectionIndex = tocChildren.indexOf(currentElement);
    }

    // Determine if this is a section or subsection.
    //var closestLi = linkElement.closest("li");
    //var isSubsection = (closestLi.parentElement.id === "toc");

    activatePage(sectionIndex);

    // Account for the nav bar.
    const navbarHeight = document.getElementById("mainHeader").offsetHeight;
    var target;

    if (isSubsection) {
        target = document.querySelector(`section[data-section-id=s-${sectionID}]`);

        if (target == null) { // Section probably hasn't loaded yet.
            target = toc;
        }
    } else {
        target = toc;
    }

    if (window.innerWidth > 768) {
        const targetPosition = target.getBoundingClientRect().top + window.scrollY;

        window.scrollTo({
            top: targetPosition - navbarHeight,
            behavior: "smooth"
        });
    } else {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

function insertFunFacts() {
    const pages = document.querySelectorAll("article .content .page");
    let lastInsertedFact = -1; // To track the last position where a fact was inserted.

    for (let i = 0; i < pages.length; i++) {
        if (pageIsLoaded(i)) {
            const page = pages[i];
            const sections = page.querySelectorAll("section");

            if (lastInsertedFact < pages.length && facts.length > 0) {
                // Randomly decide whether to drop a fact.
                if (Math.random() < 0.5) {
                    const factData = facts.pop();

                    const fact = document.createElement("div");
                    fact.className = "funFact";

                    const factIcon = document.createElement("div");
                    factIcon.className = "icon";
                    fact.appendChild(factIcon);

                    const factWrapper = document.createElement("div");
                    factWrapper.className = "wrapper";
                    fact.appendChild(factWrapper);

                    const factTitle = document.createElement("h4");
                    factTitle.className = "title";
                    factTitle.innerHTML = "Fact";
                    factWrapper.appendChild(factTitle);

                    const factContent = document.createElement("p");
                    factContent.innerHTML = factData.content_md;
                    factWrapper.appendChild(factContent);

                    let randomIndex = Math.floor(Math.random() * (sections.length - 1)) + 1;
                    if (randomIndex === sections.length) {
                        page.appendChild(fact);
                    } else {
                        page.insertBefore(fact, sections[randomIndex]);
                    }

                    lastInsertedFact = i;
                }
            }
        }
    }
}

function lookUpSelectedText() {
    if (selectedText != null && selectedText.length > 0) {
        const queryString = `proficiency=${encodeURIComponent(proficiency)}&topic=${encodeURIComponent(selectedText)}`;
        const url = `/e/new?${queryString}`;
        didSubmitNewEntry = true;
        dismissSelectionPopup();
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

function makeTOC(sections) {
    toc.innerHTML = "";

    sections.forEach(section => {
        const topLevelitem = document.createElement("li");
        toc.appendChild(topLevelitem);

        const arrow = document.createElement("span");
        arrow.className = "arrow";
        arrow.innerHTML = "⟩";
        topLevelitem.appendChild(arrow);

        const sectionTitle = document.createElement("h3");
        topLevelitem.appendChild(sectionTitle);

        const sectionTitleLink = document.createElement("a");
        sectionTitleLink.className = "section";
        sectionTitleLink.href = "#";
        sectionTitleLink.innerHTML = section.title;
        sectionTitleLink.setAttribute("data-section-id", section.id);
        sectionTitleLink.addEventListener("click", function (e) {
            e.preventDefault();
            handleTOCLinkClick(this);
        });
        sectionTitle.appendChild(sectionTitleLink);

        if (section.subsections != null) {
            const nestedList = document.createElement("ol");
            topLevelitem.appendChild(nestedList);

            section.subsections.forEach(subsection => {
                const nesteditem = document.createElement("li");
                nesteditem.id = subsection.id;
                nestedList.appendChild(nesteditem);

                const subsectionTitle = document.createElement("h4");
                nesteditem.appendChild(subsectionTitle);

                const subsectionTitleLink = document.createElement("a");
                subsectionTitleLink.className = "subsection";
                subsectionTitleLink.href = "#";
                subsectionTitleLink.innerHTML = subsection.title;
                subsectionTitleLink.setAttribute("data-section-id", subsection.id);
                subsectionTitleLink.addEventListener("click", function (e) {
                    e.preventDefault();
                    handleTOCLinkClick(this);
                });
                subsectionTitle.appendChild(subsectionTitleLink);
            });
        }
    });

    // Activate the first item.
    const firstItem = document.querySelector("#toc>li");
    firstItem.classList.add("active");
}

function pageIsLoaded(index) {
    const pages = document.querySelectorAll("article .content .page");
    let ret = false;

    if (index < pages.length) {
        const page = pages[index];
        const firstSection = page.querySelector("section");
        const firstSectionContent = firstSection.querySelector(".sectionContent");

        if (firstSectionContent != null && firstSectionContent.innerHTML != "") {
            ret = true;
        }
    }

    return ret;
}

function presentChatWindow() {
    resetChat = 1;

    var messages = chatWindowMessageList.querySelectorAll(".chatMessage");
    // Convert HTMLCollection to Array to avoid live collection issues.
    var messagesArray = Array.from(messages);
    messagesArray.forEach(function (message) {
        chatWindowMessageList.removeChild(message);
    });

    chatWindowContextLabel.textContent = `"${chatContext}"`;

    chatWindow.classList.remove("hidden");
    selectionPopup.classList.add("hidden");

    assistantInputTextarea.value = "";
    assistantInputTextarea.focus();
}

function presentSelectionPopup(sectionID, rect, allowedActions) {
    if (selectedText != null && selectedText.length > 0) {
        chatContext = selectedText;

        if (selectedText.length > 340) {
            selectedText = selectedText.substr(0, 340) + "…";
        }

        if (allowedActions.length > 0) {
            selectionPopup.querySelectorAll("button").forEach(button => {
                button.classList.add("hidden");
            });

            for (const action of allowedActions) {
                if (action == ALLOWED_POPUP_ACTIONS.ASK_ASSISTANT) {
                    askAssistantButton.classList.remove("hidden");
                }

                if (action == ALLOWED_POPUP_ACTIONS.LOOK_UP) {
                    lookUpButton.classList.remove("hidden");
                }
            }

            chatContextSectionID = sectionID;
            selectionPopup.classList.remove("hidden"); // Temporarily display to get the height.
            const popupWidth = selectionPopup.offsetWidth;

            // Center the popup above the selected text.
            const selectionMidpoint = rect.left + (rect.width / 2);
            let calculatedLeft = (selectionMidpoint - (popupWidth / 2) + window.scrollX);

            // Calculate top position to place it below the text selection.
            // rect.bottom gives the bottom of the selection rectangle relative to the viewport.
            let calculatedTop = (rect.bottom + window.scrollY + 10);

            // Check for left edge.
            if (calculatedLeft < 10) {
                calculatedLeft = 10;
            }
            // Check for right edge.
            if ((calculatedLeft + popupWidth) > window.innerWidth) {
                calculatedLeft = window.innerWidth - popupWidth - 10;
            }

            selectionPopup.style.left = calculatedLeft + "px";
            selectionPopup.style.top = calculatedTop + "px";

            shouldDisplaySelectionPopup = true;
        }
    }
}

function setUpPage() {
    setUpPageBindings();
    setUpPageEventListeners();
    // --
    insertFunFacts();
    activatePage(0);
}

function setUpPageBindings() {
    askAssistantButton = document.querySelector("#askAssistantButton");
    assistantInputForm = document.querySelector("#assistantInput");
    assistantInputTextarea = assistantInputForm.querySelector("textarea");
    accuracyNotice = document.querySelector("#accuracyNotice");
    chatWindow = document.querySelector("#chatWindow");
    chatWindowCloseButton = chatWindow.querySelector(".titlebar .windowActionButtons .close");
    chatWindowContextLabel = chatWindow.querySelector("#chatMessages .contextMessage");
    chatWindowMessageList = chatWindow.querySelector("#chatMessages");
    content = document.querySelector("article>.content");
    coverImage = document.querySelector("article #coverImage");
    coverImageProgressIndicator = coverImage.querySelector(".progressIndicator");
    coverImageSourceLabel = coverImage.querySelector(".source");
    entryProgressIndicator = document.querySelector("#entryProgressIndicator");
    lookUpButton = document.querySelector("#lookUpButton");
    newEntryForm = document.querySelector("#newEntry");
    progressOverlay = document.querySelector("#progressOverlay");
    relatedTopics = document.querySelector("#relatedTopics ul");
    relatedTopicsContainer = document.querySelector("#relatedTopics");
    selectionPopup = document.querySelector("#selectionPopup");
    toc = document.querySelector("#toc");
}

function setUpPageEventListeners() {
    askAssistantButton.addEventListener("click", function () {
        if (chatContext.length > 300) {
            dismissSelectionPopup();
            alert("Your text selection is too large. Be more specific!");
        } else {
            presentChatWindow();
        }
    });

    assistantInputForm.addEventListener("submit", function (e) {
        getChatCompletion();
        e.preventDefault();
    });

    assistantInputTextarea.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            // Prevent the default behavior (new line) and submit the form.
            e.preventDefault();
            getChatCompletion();
        }
    });

    // Listen to mousedown to hide the selection popup if clicking outside.
    document.addEventListener("mousedown", (event) => {
        if (shouldDisplaySelectionPopup && !selectionPopup.contains(event.target)) {
            dismissSelectionPopup();
            shouldDisplaySelectionPopup = false;
        }
    });

    // Listen to mouseup to potentially show the selection popup.
    document.addEventListener("mouseup", () => {
        handleTextSelection();
    });

    // Listen to touchend for touchscreen devices.
    document.addEventListener("touchend", () => {
        handleTextSelection();
    });

    chatWindowCloseButton.addEventListener("click", function () {
        dismissChatWindow();
    });

    lookUpButton.addEventListener("click", function () {
        lookUpSelectedText();
    });

    newEntryForm.addEventListener("submit", function (e) {
        e.preventDefault();
        newEntryForm.topic.blur();
        handleNewEntryRequest(newEntryForm.topic.value);
    });

    toc.querySelectorAll("a").forEach(item => {
        item.addEventListener("click", function (e) {
            e.preventDefault();
            handleTOCLinkClick(this);
        });
    });
}
