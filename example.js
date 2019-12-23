
var textContentElement = document.getElementById('textContent');
var actionResultElement = document.getElementById('actionResult');
var timeout;
var lastTap = 0;
textContentElement.addEventListener('touchend', function(event) {
    var currentTime = new Date().getTime();
    var tapLength = currentTime - lastTap;
    clearTimeout(timeout);
    if (tapLength < 300 && tapLength > 0) {
      actionResultElement.innerHTML = 'Double Tap';
      event.preventDefault();
    } else {
      actionResultElement.innerHTML = 'Single Tap';
      timeout = setTimeout(function() {
        actionResultElement.innerHTML = 'Single Tap (timeout)';
        clearTimeout(timeout);
      }, 300);
    }
    lastTap = currentTime;
});
