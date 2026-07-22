#!/usr/bin/env node

const http = require('http');
const https = require('https');
const fs = require('fs');

const baseUrl = process.env.API_URL || 'http://localhost:8000';
const schemaUrl = `${baseUrl}/api/v1/openapi.json`;
const outputFile = 'openapi.json';

console.log(`Fetching schema from: ${schemaUrl}`);

const client = schemaUrl.startsWith('https') ? https : http;

client.get(schemaUrl, (res) => {
  if (res.statusCode !== 200) {
    console.error(`Error: Server returned status ${res.statusCode}`);
    process.exit(1);
  }

  let data = '';
  res.on('data', (chunk) => (data += chunk));
  res.on('end', () => {
    fs.writeFileSync(outputFile, data, 'utf-8');
    const size = (data.length / 1024).toFixed(1);
    console.log(`✓ ${outputFile} updated! (${size} KB)`);
  });
}).on('error', (err) => {
  console.error(`Error: Could not connect to ${baseUrl}`);
  console.error(`  Make sure the backend is running.`);
  console.error(`  Details: ${err.message}`);
  process.exit(1);
});
