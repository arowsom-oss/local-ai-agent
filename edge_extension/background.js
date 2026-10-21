// Only a person clicking the extension icon grants activeTab on this tab.
chrome.action.onClicked.addListener(async tab => {
  if (!tab.id || !tab.url?.startsWith('https://')) return;
  await chrome.windows.create({url: chrome.runtime.getURL('panel.html') + '?tab=' + tab.id,
                               type: 'popup', width: 500, height: 600});
});
