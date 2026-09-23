import { Html, Head, Main, NextScript } from 'next/document';

/* WP-83: the document starts French — the signed-out pages are — and Layout
   moves `lang` to the learner's chrome language (WP-82) once it is known.
   The browser bar follows the theme: one colour per scheme here, and
   `applyVisualSettings` pins it when the learner chose a theme in Réglages. */
export default function Document() {
  return (
    <Html lang="fr">
      <Head>
        <meta name="description" content="L’Atelier — un quotidien de français." />
        <meta name="theme-color" media="(prefers-color-scheme: light)" content="#f1ece1" />
        <meta name="theme-color" media="(prefers-color-scheme: dark)" content="#171510" />
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="icon" href="/icons/atelier-mark.svg" type="image/svg+xml" />
      </Head>
      <body>
        <script
          dangerouslySetInnerHTML={{
            __html:
              "document.querySelectorAll('[data-next-hide-fouc]').forEach(function(element){element.remove();});",
          }}
        />
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
