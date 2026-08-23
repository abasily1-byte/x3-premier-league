# X3 Premier League Dashboard

An automatically updated, newspaper-style Premier League scoreboard for the
528 × 792 pixel XTEINK X3 e-reader and CrossPoint Reader.

[Download the latest PremierLeague.bmp](https://raw.githubusercontent.com/abasily1-byte/x3-premier-league/main/PremierLeague.bmp)

## How the pieces work together

- **GitHub** fetches the latest Premier League fixtures and results, then
  generates `PremierLeague.bmp` automatically.
- **Tasker** on an Android phone downloads that image as `Download/sleep.bmp`
  and sends it to the X3.
- **CrossPoint Reader** runs the X3's File Transfer web server and uses the
  uploaded `/sleep.bmp` as the custom sleep screen.

GitHub continues to publish the dashboard as `PremierLeague.bmp`; there is no
need to rename the file in this repository. Tasker gives the downloaded copy
the name `sleep.bmp` because that is the filename used by the X3.

## What it shows

- Current Premier League season and gameweek
- Completed-match count
- Final scores with `FT` status
- Live matches when present
- Upcoming fixtures
- Kickoff and update times in `America/Los_Angeles` (Pacific Time)

The generated file is an uncompressed 24-bit RGB BMP containing only pure black
and pure white pixels. No grayscale or color pixels are used.

## Data source

Version 1 uses the no-key JSON data endpoint served by
[PremierLeague.com](https://www.premierleague.com/). It supplies season,
gameweek, fixture, score, status, kickoff, and team data. No API key or GitHub
secret is required.

## Automation

The [GitHub Actions workflow](.github/workflows/update.yml):

- runs automatically at minute 17 of every hour (UTC);
- can also be run manually with **Run workflow**;
- prevents concurrent runs on the same branch;
- validates the output before committing it; and
- commits `PremierLeague.bmp` only when the generated file changed.

GitHub Actions schedules can be delayed during periods of high service load.

## Automatic X3 sleep-screen updates

### 1. Prepare CrossPoint Reader

On the X3:

1. Place or use `sleep.bmp` in the root of the SD card.
2. Select the **Custom sleep-screen** option in CrossPoint Reader.
3. Open **File Transfer → Join Network** whenever you want to refresh the
   dashboard.

The File Transfer screen displays the X3's current IP address. Replace
`<X3-IP>` in the Tasker actions below with that address. For example, one X3
used `192.168.0.28`, but this is only an example: your router may assign a
different address, and that address can change later.

Keep the phone and X3 on the same local network while running the task.

### 2. Create the Tasker task

Add these three **HTTP Request** actions to one Tasker task, in this order.

#### Action 1 — Download the latest dashboard

- **Method:** `GET`
- **URL:**

  ```text
  https://raw.githubusercontent.com/abasily1-byte/x3-premier-league/main/PremierLeague.bmp
  ```

- **File To Save With Output:**

  ```text
  Download/sleep.bmp
  ```

This downloads GitHub's `PremierLeague.bmp` while saving the phone's local copy
under the X3-compatible name `sleep.bmp`.

#### Action 2 — Delete the old sleep screen from the X3

- **Method:** `POST`
- **URL:**

  ```text
  http://<X3-IP>/delete
  ```

- **Body:**

  ```text
  path=/sleep.bmp
  ```

#### Action 3 — Upload the new sleep screen

- **Method:** `POST`
- **URL:**

  ```text
  http://<X3-IP>/upload?path=/
  ```

- **Body:**

  ```text
  x=1
  ```

- **File To Send:**

  ```text
  file:Download/sleep.bmp
  ```

### 3. Refresh the sleep screen

1. On the X3, open **File Transfer → Join Network**.
2. Run the Tasker task.
3. Wait a few seconds for the delete and upload actions to finish.
4. Exit File Transfer.
5. Put the X3 to sleep.

The newly uploaded `sleep.bmp` should appear as the updated Premier League
sleep screen. Because Tasker always replaces the same root file, you should not
need to select the custom sleep-screen image again after each update.

### Android `.local` hostname note

`http://crosspoint.local` may work on some phones, but Android sometimes fails
to resolve `.local` hostnames. If Tasker reports an error such as:

```text
UnknownHostException: Unable to resolve host "crosspoint.local"
```

replace `crosspoint.local` in the Tasker URLs with the numeric IP address shown
on the X3 after choosing **File Transfer → Join Network**.

For a more permanent setup, you can optionally reserve the X3's IP address in
your router's DHCP settings. The exact steps depend on the router.

## Optional NFC automation

The Tasker task can also be triggered by an NFC tag:

1. In Tasker, open **Profiles → + → Event → Net → NFC Tag**.
2. Scan an NFC tag.
3. Associate that profile with the Premier League update task.

The everyday workflow then becomes:

**X3 → File Transfer → Join Network → tap the phone on the NFC tag → wait a few
seconds → exit File Transfer → sleep**

## Repository behavior

- GitHub generates and publishes `PremierLeague.bmp`; it does not need to be
  renamed in the repository.
- Tasker downloads that file locally as `Download/sleep.bmp`.
- The GitHub Action refreshes the Premier League dashboard automatically.
- No API key or repository secret is required.
- This repository is public, so other users may clone, fork, or adapt it.

## Run locally

```bash
python -m pip install -r requirements.txt
python generate_pl_bmp.py --validate
```

To validate an existing output without fetching data:

```bash
python generate_pl_bmp.py --validate-only
```

The generator prints every displayed fixture and result so its output can be
compared directly with the source response in CI logs.
