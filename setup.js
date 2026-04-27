// Run this ONCE to set up Back4App classes
// Usage: node setup.js

const https = require('https');

const PARSE_APP_ID = "qXJqQ3HWKYsGVB1oQKnYZo7zdNLHgjZMiwonhozr";
const PARSE_REST_KEY = "mdTfymJLDHJY46HUv0tgKtWkqMm4YHQEbdsPX8tJ";
const PARSE_HOST = "parseapi.back4app.com";

const HEADERS = {
    "X-Parse-Application-Id": PARSE_APP_ID,
    "X-Parse-REST-API-Key": PARSE_REST_KEY,
    "Content-Type": "application/json"
};

function request(method, path, body = null) {
    return new Promise((resolve, reject) => {
        const options = {
            hostname: PARSE_HOST,
            path: path,
            method: method,
            headers: HEADERS
        };
        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                console.log(`${method} ${path} → ${res.statusCode}`);
                try { resolve(JSON.parse(data)); } catch(e) { resolve(data); }
            });
        });
        req.on('error', reject);
        if (body) req.write(JSON.stringify(body));
        req.end();
    });
}

async function setup() {
    console.log('🔧 Setting up Back4App classes...\n');
    
    // Create Index class with a test object
    console.log('Creating Index class...');
    await request('POST', '/classes/Index', {
        data: '{"index":{},"urls":[],"titles":[],"snippets":[],"doc_count":0,"timestamp":0}',
        docCount: 0,
        timestamp: 0
    });
    
    // Create CrawlQueue class with a test object
    console.log('Creating CrawlQueue class...');
    await request('POST', '/classes/CrawlQueue', {
        url: 'https://example.com',
        status: 'done'
    });
    
    // Add seed URLs to queue
    console.log('\n📝 Adding seed URLs...');
    const seeds = [
        "https://en.wikipedia.org/wiki/Search_engine",
        "https://en.wikipedia.org/wiki/Web_crawler",
        "https://developer.mozilla.org/en-US/",
        "https://www.python.org/",
        "https://github.com/"
    ];
    
    for (const url of seeds) {
        await request('POST', '/classes/CrawlQueue', { url, status: 'pending' });
    }
    
    console.log('\n✅ Setup complete!');
    console.log('Push to GitHub and the crawler will run automatically.');
    console.log('Or trigger it manually from the Actions tab.');
}

setup().catch(console.error);
