import { Html, Head, Main, NextScript } from 'next/document';

export default function Document() {
  return (
    <Html lang="de">
      <Head>
        <meta name="description" content="Conversational Language Learning Platform" />
        <meta name="theme-color" content="#f1ece1" />
        <link rel="icon" href="/favicon.ico" />
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
