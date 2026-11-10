# Site-wide WordPress content

Contains site configuration and the **customized** WordPress sidebar, navigation, and shared assets.

- `site/site.json` contains public, non-secret settings, not account credentials.
- `site/template-parts/sidebar.wp.html` preserves the site's custom sidebar block markup.
- `site/navigation/wp-31.wp.html` preserves the site's site-wide navigation.
- `site/shared-media.json` lists original shared media for a verified binary download.
- `media/wp-45/` contains the original footer/sidebar image and its checksum after import.

Theme-default templates are **not** duplicated in this snapshot; the active theme is `pub/nook`. Articles, pages, and their media remain separate imports.

To download shared assets locally (requires internet access):

```bash
python tools/fetch_wordpress_media.py --manifest site/shared-media.json
```

The script does **not** modify WordPress. Use ordinary Git blobs, not Git LFS.
