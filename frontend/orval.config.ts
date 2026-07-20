import { defineConfig } from 'orval';

export default defineConfig({
  talkfiesta: {
    input: './openapi.json',
    output: {
      mode: 'tags-split',
      target: './lib/api/generated/talkfiesta.ts',
      schemas: './lib/api/generated/schemas',
      client: 'react-query',
      httpClient: 'axios',
      override: {
        mutator: {
          path: './lib/api/axios.ts',
          name: 'customInstance',
        },
      },
    },
  },
});
