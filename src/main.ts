import { mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { fetchShopSnapshot } from "./shopClient.ts";
import { diffSnapshots } from "./diff.ts";
import { buildBaselineReport, buildReport } from "./report.ts";
import { ChangeKind, type Snapshot } from "./types.ts";

const logger = {
  info(message: string): void {
    console.log(`[shop-watch] ${message}`);
  },
  error(message: string): void {
    console.error(`[shop-watch] ERROR ${message}`);
  },
};

const SNAPSHOT_PATH = process.env.SNAPSHOT_PATH ?? "data/shop-latest.json";
const REPORTS_DIR = process.env.REPORTS_DIR ?? "reports";

async function loadPreviousSnapshot(): Promise<Snapshot | null> {
  try {
    const raw = await readFile(SNAPSHOT_PATH, "utf8");
    return JSON.parse(raw) as Snapshot;
  } catch {
    return null;
  }
}

function shopDateKey(date: string): string {
  return date.slice(0, 10);
}

async function main(): Promise<void> {
  const snapshot = await fetchShopSnapshot();
  const previous = await loadPreviousSnapshot();
  await mkdir(REPORTS_DIR, { recursive: true });
  const reportPath = `${REPORTS_DIR}/${shopDateKey(snapshot.date)}.md`;
  const displayDate = shopDateKey(snapshot.date).split("-").reverse().join("/");
  const previousDisplayDate = previous === null ? null : shopDateKey(previous.date).split("-").reverse().join("/");
  if (previous === null) {
    await writeFile(reportPath, buildBaselineReport(displayDate, snapshot.offers));
    logger.info(`baseline seeded: ${snapshot.offers.length} offers`);
  } else {
    const changes = diffSnapshots(previous, snapshot);
    const changesJsonPath = `${REPORTS_DIR}/${shopDateKey(snapshot.date)}.json`;
    if (changes.length === 0 && existsSync(reportPath)) {
      logger.info("added=0 removed=0 priceChanged=0 (existing report kept)");
    } else {
      await writeFile(reportPath, buildReport(displayDate, previousDisplayDate, changes));
      await writeFile(changesJsonPath, JSON.stringify({ shopDate: displayDate, previousDate: previousDisplayDate, changes }, null, 2) + "\n");
      const added = changes.filter((c) => c.kind === ChangeKind.Added).length;
      const removed = changes.filter((c) => c.kind === ChangeKind.Removed).length;
      const priceChanged = changes.filter((c) => c.kind === ChangeKind.PriceChanged).length;
      logger.info(`added=${added} removed=${removed} priceChanged=${priceChanged}`);
    }
  }
  await writeFile(SNAPSHOT_PATH, JSON.stringify(snapshot, null, 2) + "\n");
}

main().catch((error: unknown) => {
  logger.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
