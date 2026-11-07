# Get Going Fast local app style guide

The reference header is shown in [app-header-reference.png](app-header-reference.png). Use it as the shared header pattern for GGF local apps, including desktop and phone views.

## Header

Build a rounded dark blue header with a subtle navy-to-blue gradient, a thin blue border, and three desktop columns:

1. Left: `GET GOING FAST · LOCAL AI` in small tracked gold capitals, the app's real product name in large gold type, one short benefit sentence, then links labeled `GetGoingFast.pro ↗` and `TheAIHobbyGuy ↗`.
2. Center: the exact two-line slogan `Your Time Is Limited.` and `Get Going Fast.` Center it, set the first line white and the second gold.
3. Right: the [GGF brain icon](ggf-brain-logo.png), square and uncropped, with useful alternative text. Use the same icon in every app. Bundle it locally so the header works offline and on a phone link.

Use the product's actual public name in the visible heading and browser title. For this app the name is **Viggle Recast**. Internal paths and identifiers can retain established names.

## Style values

| Part | Value |
| --- | --- |
| Header background | `linear-gradient(135deg, #0b1220, #172554)` |
| Border | `1px solid #334a6b`, `18px` radius |
| Heading and second slogan line | `#f5b942` |
| First slogan line | `#f4f7fc` |
| Body copy | `#dbeafe` |
| Links | `#9dcbff`, underlined |
| Desktop padding and gap | `25px 28px`, `20px` gap |
| Desktop icon | `120px` square |

Keep links keyboard focusable with a visible gold focus outline. The icon must not cover the slogan or the product copy.

## Phone layout

At widths under `900px`, put the copy and icon on the first row and move the slogan to a full-width second row. Reduce the icon to about `96px`. Under `680px`, give the copy the full first row, then place the slogan beside a `72px` icon. Use `18px` padding and a slogan around `1.25rem`. Let links wrap. Check the result at a phone width near `390px` and at desktop width before release.

Keep the header's images local and embedded when an app is served over LAN or a temporary phone link. The same design applies whether the app uses Gradio or another UI framework.
