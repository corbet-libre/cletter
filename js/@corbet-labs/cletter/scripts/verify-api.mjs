// This module also runs in a real browser with no Node shims.
export function verify(api) {
    const check = (actual, expected) => {
        if (JSON.stringify(actual) !== JSON.stringify(expected)) {
            throw new Error(`${JSON.stringify(actual)} !== ${JSON.stringify(expected)}`);
        }
    };
    check(api.salutation('de-ch', 'Frau Dr. Müller'), 'Sehr geehrte Frau Dr. Müller');
    check(api.salutationSupported('de-ch'), true);
    check(api.salutationSupported('xx'), false);
    check(api.salutationHonorific('de-ch', 'Frau Dr. Müller'), 'Frau');
    check(api.closing('de-ch'), 'Freundliche Grüsse');
    check(api.longDate('de-ch', 2026, 9, 7), '7. September 2026');
    check(api.resolveLocale('de', 'Zürich, Zug'), 'de-ch');
    check(api.normalizeLanguage('DE_li'), 'de-li');
    check(api.normalizeLocaleId(' EN_CH '), 'en-ch');
    check(api.normalizeLocaleId('zh_Hant_TW'), 'zh-hant-tw');
    check(api.closing('de-li'), 'Freundliche Grüsse');
    check(api.orthographyIssues('de-li', 'Grüße GROẞ'), [['ß', 'ss'], ['ẞ', 'SS']]);
    check(api.applyOrtho('de-li', 'Grüße GROẞ'), 'Grüsse GROSS');
}
