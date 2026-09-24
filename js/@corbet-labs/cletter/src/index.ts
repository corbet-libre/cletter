/**
 * Locale-correct business correspondence, composed from focused units.
 *
 * Pure TypeScript port of the cletter Rust crate: zero dependencies of its
 * own (it re-exports @corbet-labs/cnice, @corbet-labs/cdate and
 * @corbet-labs/cink), zero Node APIs, synchronous, no I/O.
 *
 * One locale per document (BCP 47). Unknown locales fall back through the
 * base language to English. Explicit overrides always win — tables supply
 * defaults, never commands.
 */
import { LETTER_TABLES } from './generated/tables.ts';

import { greet, farewell } from '@corbet-labs/cnice';
export const closing = farewell.closing;
export const availableLocales = farewell.availableLocales;
export const salutationHonorific = greet.salutationHonorific;
export const salutationTitles = greet.salutationTitles;
export const salutationSurname = greet.salutationSurname;
export const salutationLastName = greet.salutationLastName;
export const recipientSalutationWarning = greet.recipientSalutationWarning;
export const honorificWarning = greet.honorificWarning;
export const salutationSupported = greet.isSupported;
export {
    normalize,
    exceedsLimits,
    scaleToFit,
    signatureSize,
    imageSnippet,
    defaultMaxPixels,
    supportedFormats,
    type DecodedImage,
    type ImageMime,
} from '@corbet-labs/cink';
// availableLocales stays with its owner: cnice::farewell's
// availableLocales is already re-exported above, and salutation coverage
// questions are answered by the re-exported salutationSupported above.
export {
    longDate,
    mediumDate,
    shortDate,
    monthYear,
    isValidDate,
} from '@corbet-labs/cdate';
// Re-exported `greet` consts above (recipientSalutationWarning,
// honorificWarning, salutationSupported) are module-scope and used directly
// below; covered-locale rendering itself goes through greet.salutation.

interface LocaleEntry {
    formal: string;
    named: string;
    subject_prefix: string;
    subject_unsolicited: string;
    use_ss: boolean;
}

interface LocalesFile {
    locales: Record<string, LocaleEntry>;
    supported: string[];
    fallback: string;
    variants: Record<string, Record<string, string>>;
    orthography_replacements: ReadonlyArray<readonly [string, string]>;
}

interface CountriesFile {
    keywords: Record<string, string>;
    cantons: string[];
}

interface Tables {
    LOCALES: LocalesFile;
    COUNTRIES: CountriesFile;
}

const { LOCALES, COUNTRIES } = LETTER_TABLES as unknown as Tables;

function baseLanguage(code: string): string {
    return code.split('-')[0] ?? code;
}

/**
 * Normalize an explicit locale ID's spelling without inference or fallback.
 * Trim only ASCII space, tab, LF, CR, VT and FF; replace underscores with
 * hyphens and lowercase ASCII letters. Preserve other characters.
 * Preserve all subtags, including those absent from correspondence tables.
 * This does not validate syntax or registry support; empty input stays empty.
 */
export function normalizeLocaleId(input: string): string {
    return input
        .replace(/^[ \t\n\r\v\f]+|[ \t\n\r\v\f]+$/g, '')
        .replace(/_/g, '-')
        .replace(/[A-Z]/g, (letter) => letter.toLowerCase());
}

/** Normalize a loose language string to a supported lowercase BCP 47 code. */
export function normalizeLanguage(input: string): string | null {
    const lower = input.trim().replace(/_/g, '-').toLowerCase();
    if (LOCALES.supported.includes(lower)) return lower;
    const base = baseLanguage(lower);
    return LOCALES.supported.includes(base) ? base : null;
}

/**
 * Extract an uppercase ISO country code from a free-text location:
 * country keywords first, then Swiss cantons.
 */
export function countryFromLocation(location: string): string | null {
    const trimmed = location.toLowerCase().trim();
    if (trimmed === '') return null;
    for (const [keyword, code] of Object.entries(COUNTRIES.keywords)) {
        if (trimmed.includes(keyword)) return code;
    }
    for (const part of trimmed.split(/[,;]/).map((s) => s.trim())) {
        if ((COUNTRIES.cantons as string[]).includes(part)) return 'CH';
    }
    return null;
}

/**
 * Resolve a language plus an optional free-text location to a BCP 47
 * locale. No location preserves the normalized language.
 */
export function resolveLocale(language?: string, location?: string): string {
    const normalized = (language !== undefined ? normalizeLanguage(language) : null) ?? 'en';
    const base = baseLanguage(normalized);
    const country = location !== undefined ? countryFromLocation(location) : null;
    if (country === null) return normalized;
    return LOCALES.variants[base]?.[country] ?? base;
}

function resolveKey(locale: string): string {
    const lower = locale.toLowerCase();
    if (Object.hasOwn(LOCALES.locales, lower)) return lower;
    const base = baseLanguage(lower);
    return Object.hasOwn(LOCALES.locales, base) ? base : LOCALES.fallback;
}

/**
 * Opening line: when a name is given for a locale covered by the uniform
 * salutation renderer, the name is parsed and rendered the same way as
 * `salutation`; otherwise the `named` template is filled verbatim, or the
 * formal address when no name is given. An explicit override always wins.
 */
export function opening(locale: string, name?: string, overrideOpening?: string): string {
    if (overrideOpening !== undefined) return overrideOpening;
    const clean = name?.trim();
    if (clean !== undefined && clean !== '') {
        if (salutationSupported(locale)) return greet.salutation(locale, clean);
        const entry = LOCALES.locales[resolveKey(locale)];
        return entry.named.replace('{name}', clean);
    }
    return LOCALES.locales[resolveKey(locale)].formal;
}

/**
 * Subject line: prefix plus title, or the unsolicited-subject default when
 * no title is known. The override replaces the prefix only.
 */
export function subject(locale: string, title?: string, prefixOverride?: string): string {
    const entry = LOCALES.locales[resolveKey(locale)];
    const clean = title?.trim();
    if (clean !== undefined && clean !== '') {
        return `${prefixOverride ?? entry.subject_prefix} ${clean}`;
    }
    return entry.subject_unsolicited;
}

/**
 * Locale-correct salutation through the uniform renderer for every locale it
 * covers (no per-language branch: coverage is data in the salutation tables);
 * all other locales resolve the opening template.
 */
export function salutation(locale: string, name: string): string {
    if (salutationSupported(locale)) return greet.salutation(locale, name);
    return opening(locale, name);
}

/** Literal source/replacement pairs for the locale, in table order. */
export function orthographyReplacements(locale: string): ReadonlyArray<readonly [string, string]> {
    return LOCALES.locales[resolveKey(locale)].use_ss
        ? LOCALES.orthography_replacements.map(([source, replacement]) => [source, replacement] as const)
        : [];
}

/**
 * Non-mutating diagnostics: each applicable pair present in text, once.
 * Pass generated prose only; callers exclude names, quotations, URLs and sources.
 */
export function orthographyIssues(locale: string, text: string): ReadonlyArray<readonly [string, string]> {
    return orthographyReplacements(locale).filter(([source]) => text.includes(source));
}

/**
 * Apply literal spelling substitutions to caller-selected prose. Swiss and
 * Liechtenstein German use ss/SS. Exclude protected names, quotations, URLs and
 * source material first, or use orthographyIssues without changing the text.
 * Opening, subject, closing and overrides are never transformed implicitly.
 */
export function applyOrtho(locale: string, text: string): string {
    return orthographyReplacements(locale).reduce(
        (result, [source, replacement]) => result.split(source).join(replacement), text,
    );
}

/**
 * Non-blocking advisories for a recipient name: the missing-name warning in
 * every locale, the honorific warning wherever the uniform renderer applies.
 * Empty means the record is clean.
 */
export function warnings(location: string, locale: string, name: string): string[] {
    const out: string[] = [];
    const missing = recipientSalutationWarning(location, name);
    if (missing !== null) out.push(missing);
    if (salutationSupported(locale)) {
        const honorific = honorificWarning(location, locale, name);
        if (honorific !== null) out.push(honorific);
    }
    return out;
}
