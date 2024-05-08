const gmail_status = document.getElementById("gmail-status");
const trello_status = document.getElementById("trello-status");
const user = document.getElementById("user-data");

function changeColors() {
  if (gmail_status.innerHTML === "Declined") {
    gmail_status.style.color = "red";
  }
  if (trello_status.innerHTML === "Declined") {
    trello_status.style.color = "red";
  }
  if (gmail_status.innerHTML === "Accepted") {
    gmail_status.style.color = "green";
  }
  if (trello_status.innerHTML === "Accepted") {
    trello_status.style.color = "green";
  }
}

changeColors();
