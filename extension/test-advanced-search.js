// Test script for advanced search functionality
// Run this in the browser console when the extension is loaded on echomtg.com

async function testAdvancedSearch() {
  console.log('=== Testing Advanced Search ===');
  
  try {
    // Test different search patterns
    const testQueries = [
      { query: 'SF', expected: 'initials' },
      { query: 'S F', expected: 'space_initials' },
      { query: 'storm fal', expected: 'multi_token' },
      { query: 'sto', expected: 'prefix' },
      { query: 'T', expected: 'prefix' }
    ];
    
    for (const test of testQueries) {
      console.log(`\nTesting: "${test.query}"`);
      
      // Test search
      const result = await chrome.runtime.sendMessage({
        type: 'SEARCH_CARDS',
        query: test.query,
        activeSets: [] // Search all cached sets
      });
      
      if (result.ok) {
        console.log(`✓ Search successful for "${test.query}"`);
        console.log(`  Expected strategy: ${test.expected}`);
        console.log(`  Results found: ${result.cards.length}`);
        
        if (result.cards.length > 0) {
          console.log('  Top 3 results:');
          result.cards.slice(0, 3).forEach((card, i) => {
            console.log(`    ${i + 1}. ${card.name} (${card.set_code})`);
          });
        }
      } else {
        console.log(`✗ Search failed for "${test.query}": ${result.error}`);
      }
    }
    
  } catch (error) {
    console.error('Test failed:', error);
  }
}

console.log('Advanced search test function created. Run testAdvancedSearch() to test.');
console.log('Make sure you have some cached sets first!');