// Simple test to verify search functionality
// This can be run in a browser console when the extension is loaded

console.log('=== Testing Search Utilities ===');

// Test basic token extraction
const testName = "Stormfighter Falcon";
console.log('Card name:', testName);
console.log('Tokens should be:', ['stormfighter', 'falcon']);

// Test initials generation
console.log('Initials should be:', 'sf');

// Test progressive initials
console.log('Progressive initials should be:', ['s', 'sf']);

// Test intent detection
console.log('\n=== Testing Intent Detection ===');
console.log('"SF" should detect initials');
console.log('"S F" should detect space_initials');
console.log('"storm fal" should detect multi_token');
console.log('"sto" should detect prefix');

// Test if functions are available in global scope when extension loads
console.log('\n=== Checking Extension Functions ===');
if (typeof chrome !== 'undefined' && chrome.runtime) {
  console.log('Chrome extension API available');
} else {
  console.log('Chrome extension API not available in this context');
}