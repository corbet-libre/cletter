// Copy next to a fresh installation to test the actual npm tarball.
import { createRequire } from 'node:module';
import { verify } from './verify-api.mjs';
verify(await import('@corbet-foss/cletter'));
verify(createRequire(import.meta.url)('@corbet-foss/cletter'));
verify(await import('@corbet-foss/cletter/browser'));
console.log('cletter: installed ESM, CommonJS, and browser exports passed');
