import type { languages } from 'monaco-editor';

export const ROBOT_LANGUAGE_ID = 'robot';

export const robotLanguageConfig: languages.LanguageConfiguration = {
  comments: { lineComment: '#' },
  brackets: [
    ['{', '}'],
    ['[', ']'],
    ['(', ')'],
  ],
  autoClosingPairs: [
    { open: '{', close: '}' },
    { open: '[', close: ']' },
    { open: '(', close: ')' },
    { open: '"', close: '"' },
    { open: "'", close: "'" },
  ],
};

export const robotTokensProvider: languages.IMonarchLanguage = {
  defaultToken: '',
  ignoreCase: true,

  keywords: [
    'Library', 'Resource', 'Variables', 'Documentation', 'Metadata',
    'Suite Setup', 'Suite Teardown', 'Test Setup', 'Test Teardown',
    'Test Template', 'Test Timeout', 'Force Tags', 'Default Tags',
    'RETURN', 'IF', 'ELSE', 'ELSE IF', 'END', 'FOR', 'IN', 'IN RANGE',
    'WHILE', 'TRY', 'EXCEPT', 'FINALLY', 'BREAK', 'CONTINUE',
  ],

  builtinKeywords: [
    'Log', 'Log To Console', 'Sleep', 'Set Variable', 'Should Be Equal',
    'Should Contain', 'Should Not Be Empty', 'Run Keyword', 'Run Keyword If',
    'Wait Until Keyword Succeeds', 'Set Test Variable', 'Set Suite Variable',
    'Set Global Variable', 'Get Variable Value', 'Variable Should Exist',
    'Evaluate', 'Import Library', 'Fail', 'Pass Execution', 'No Operation',
    // Browser library
    'New Browser', 'New Page', 'New Context', 'Close Browser', 'Close Page',
    'Click', 'Fill Text', 'Type Text', 'Check Checkbox', 'Uncheck Checkbox',
    'Select Options By', 'Get Text', 'Get Attribute', 'Get Property',
    'Wait For Load State', 'Wait For Elements State',
    'Go To', 'Get Url', 'Take Screenshot',
    'Keyboard Key', 'Scroll By', 'Hover', 'Focus', 'Drag And Drop',
    // SeleniumLibrary
    'Open Browser', 'Close All Browsers', 'Maximize Browser Window',
    'Click Element', 'Click Button', 'Click Link', 'Double Click Element',
    'Input Text', 'Input Password', 'Clear Element Text', 'Press Keys',
    'Select From List By Value', 'Select From List By Label',
    'Wait Until Element Is Visible', 'Wait Until Element Is Enabled',
    'Wait Until Page Contains', 'Wait Until Page Contains Element',
    'Element Should Be Visible', 'Element Should Contain',
    'Page Should Contain', 'Page Should Contain Element',
    'Get Element Attribute', 'Get Text', 'Get Value', 'Get Title',
    'Execute JavaScript', 'Set Selenium Implicit Wait',
    'Capture Page Screenshot', 'Set Browser Implicit Wait',
  ],

  tokenizer: {
    root: [
      // Section headers: *** Settings ***, *** Test Cases ***, etc.
      [/^\*\*\*\s*.+?\s*\*\*\*/, 'keyword.section'],

      // Comments
      [/#.*$/, 'comment'],

      // Variables: ${var}, @{list}, %{env}, &{dict}
      [/[$@%&]\{[^}]*\}/, 'variable'],

      // Tags/metadata in square brackets: [Tags], [Setup], [Teardown], etc.
      [/\[(Tags|Setup|Teardown|Documentation|Template|Timeout|Arguments|Return)\]/i, 'keyword.tag'],

      // Strings
      [/"[^"]*"/, 'string'],
      [/'[^']*'/, 'string'],

      // Numbers
      [/\b\d+(\.\d+)?\b/, 'number'],

      // Selectors and locators (common patterns)
      [/\b(css|xpath|id|name|class|tag|link|partial link):/, 'type'],
      [/\b(role|text|data-testid|data-cy|data-qa|aria-label)=/, 'type'],

      // Named arguments: arg=value
      [/\b\w+=/, 'attribute.name'],

      // URLs
      [/https?:\/\/[^\s]+/, 'string.link'],

      // Keywords at start of line (after 4+ spaces or tab)
      [/^(?:    |\t)+[A-Z][a-zA-Z ]+(?=    |\t|$)/, {
        cases: {
          '@builtinKeywords': 'support.function',
          '@default': 'identifier',
        },
      }],

      // Section-level names (test case names, keyword names)
      [/^[A-Za-z][A-Za-z0-9 _-]+$/, 'entity.name'],

      // Boolean-like
      [/\b(True|False|None|true|false|none|YES|NO|ON|OFF)\b/, 'constant'],

      // Remaining text
      [/[a-zA-Z_]\w*/, {
        cases: {
          '@keywords': 'keyword',
          '@builtinKeywords': 'support.function',
          '@default': 'identifier',
        },
      }],
    ],
  },
};
