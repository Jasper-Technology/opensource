import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Jasper Documentation',
  tagline: 'Open-source chemical process simulation engine',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  url: 'https://docs.jaspertech.org',
  baseUrl: '/',

  organizationName: 'Jasper-Technology',
  projectName: 'opensource',

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: '/',
          editUrl: 'https://github.com/Jasper-Technology/opensource/tree/main/docs/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    colorMode: {
      defaultMode: 'dark',
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Jasper',
      logo: {
        alt: 'Jasper Logo',
        src: 'img/jasper-logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'https://jaspertech.org',
          label: 'Launch App',
          position: 'right',
        },
        {
          href: 'https://github.com/Jasper-Technology/opensource',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [
            {
              label: 'Getting Started',
              to: '/',
            },
            {
              label: 'Thermodynamics',
              to: '/thermodynamics/overview',
            },
            {
              label: 'Unit Operations',
              to: '/unit-operations/feed',
            },
          ],
        },
        {
          title: 'Resources',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/Jasper-Technology/opensource',
            },
            {
              label: 'Main Site',
              href: 'https://jaspertech.org',
            },
          ],
        },
        {
          title: 'Legal',
          items: [
            {
              label: 'Privacy',
              href: 'https://jaspertech.org/privacy',
            },
            {
              label: 'Terms',
              href: 'https://jaspertech.org/terms',
            },
          ],
        },
      ],
      copyright: `Copyright ${new Date().getFullYear()} Jasper Technology. MIT License.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['typescript', 'bash'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
