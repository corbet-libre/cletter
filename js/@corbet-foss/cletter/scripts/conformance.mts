/**
 * TypeScript side of the cross-language conformance gate: runs every
 * `tests/vectors/*.json` vector through `src/index.ts` and compares with
 * `expected` exactly. Exits non-zero with the first mismatch.
 *
 * Run from the package root:
 *   bun ./scripts/conformance.mts
 */
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { normalizeLocaleId, normalizeLanguage, countryFromLocation, orthographyReplacements, orthographyIssues, applyOrtho, opening, resolveLocale, salutation, subject, warnings, longDate, mediumDate, shortDate, monthYear } from '../src/index.js';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');

interface Vector {
    name: string;
    fn: string;
    locale: string;
    language?: string;
    location?: string;
    person?: string;
    override?: string;
    title?: string;
    prefix_override?: string;
    text?: string;
    input?: string;
    year?: number;
    month?: number;
    day?: number;
    expected: unknown;
}

function runVector(file: string, vector: Vector): void {
    const what = `${file} :: ${vector.name}`;
    let actual: unknown;
    switch (vector.fn) {
        case 'normalize_locale_id':
            actual = normalizeLocaleId(vector.input ?? '');
            break;
        case 'normalize_language':
            actual = normalizeLanguage(vector.input ?? '');
            break;
        case 'country_from_location':
            actual = countryFromLocation(vector.input ?? '');
            break;
        case 'orthography_replacements':
            actual = orthographyReplacements(vector.locale);
            break;
        case 'orthography_issues':
            actual = orthographyIssues(vector.locale, vector.text ?? '');
            break;
        case 'resolve_locale':
            actual = resolveLocale(vector.language, vector.location);
            break;
        case 'opening':
            actual = opening(vector.locale, vector.person, vector.override);
            break;
        case 'subject':
            actual = subject(vector.locale, vector.title, vector.prefix_override);
            break;
        case 'salutation':
            actual = salutation(vector.locale, vector.person ?? '');
            break;
        case 'apply_ortho':
            actual = applyOrtho(vector.locale, vector.text ?? '');
            break;
        case 'warnings':
            actual = warnings(vector.location ?? '', vector.locale, vector.person ?? '');
            break;
        case 'long_date':
            actual = longDate(vector.locale, vector.year ?? 0, vector.month ?? 0, vector.day ?? 1);
            break;
        case 'medium_date':
            actual = mediumDate(vector.locale, vector.year ?? 0, vector.month ?? 0, vector.day ?? 1);
            break;
        case 'short_date':
            actual = shortDate(vector.locale, vector.year ?? 0, vector.month ?? 0, vector.day ?? 1);
            break;
        case 'month_year':
            actual = monthYear(vector.locale, vector.year ?? 0, vector.month ?? 0);
            break;
        default:
            throw new Error(`${what}: unknown fn ${vector.fn}`);
    }
    const got = JSON.stringify(actual) ?? 'undefined';
    const want = JSON.stringify(vector.expected) ?? 'undefined';
    if (got !== want) throw new Error(`${what}: ${got} vs ${want}`);
}

const dir = join(ROOT, 'tests/vectors');
const files = readdirSync(dir)
    .filter((file) => file.endsWith('.json'))
    .sort();
if (files.length === 0) throw new Error('no vector files in tests/vectors');
let count = 0;
for (const file of files) {
    const vectors = JSON.parse(readFileSync(join(dir, file), 'utf8')) as Vector[];
    for (const vector of vectors) {
        runVector(file, vector);
        count += 1;
    }
}
console.log(`TS conformance green: ${count} vectors across ${files.length} files`);
