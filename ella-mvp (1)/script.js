
const messagesDiv = document.getElementById('messages');
const input = document.getElementById('user-input');

function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  appendMessage('You', text);
  input.value = '';

  // Simulated AI response
  setTimeout(() => {
    const response = getEllaResponse(text);
    appendMessage('Ella', response);
  }, 600);
}

function appendMessage(sender, message) {
  const msg = document.createElement('div');
  msg.innerHTML = `<strong>${sender}:</strong> ${message}`;
  messagesDiv.appendChild(msg);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function getEllaResponse(text) {
  return "I'm Ella – here to support your fitness, mental clarity, and calm. Stay grounded, breathe deep, and let’s move forward together.";
}
