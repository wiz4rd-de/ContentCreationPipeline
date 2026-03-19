#!/usr/bin/env node
// Cleanup script for old output directories.
// Removes output/YYYY-MM-DD_*/ directories older than a configurable retention period.
//
// Usage:
//   node scripts/clean-output.mjs [--older-than <days>] [--dry-run] [--output-dir <path>]
//
// Options:
//   --older-than <days>   — retention period in days (default: 30)
//   --dry-run             — preview what would be deleted without actually deleting
//   --output-dir <path>   — path to output directory (default: output/)

import { readdirSync, statSync, rmSync } from 'node:fs';
import { resolve, basename, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- Argument parsing ---

/**
 * Parse command-line arguments.
 *
 * @param {string[]} argv
 * @returns {object}
 */
export function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--older-than') {
      args.olderThan = argv[i + 1];
      i++;
    } else if (argv[i] === '--dry-run') {
      args.dryRun = true;
    } else if (argv[i] === '--output-dir') {
      args.outputDir = argv[i + 1];
      i++;
    }
  }
  return args;
}

// --- Date parsing and age calculation ---

/**
 * Parse a directory name to extract the date prefix.
 * Pattern: YYYY-MM-DD_*
 * Returns null if the name doesn't match or the date is invalid.
 *
 * @param {string} dirName
 * @returns {Date|null}
 */
export function parseDateFromDirName(dirName) {
  const datePattern = /^(\d{4})-(\d{2})-(\d{2})_/;
  const match = dirName.match(datePattern);
  if (match === null) {
    return null;
  }

  const year = parseInt(match[1], 10);
  const month = parseInt(match[2], 10);
  const day = parseInt(match[3], 10);

  const date = new Date(year, month - 1, day, 0, 0, 0, 0);

  // Validate: reconstructing the date should match the input
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    return null;
  }

  return date;
}

/**
 * Calculate age in days between a date and now.
 *
 * @param {Date} date
 * @returns {number}
 */
export function calculateAgeDays(date) {
  const now = Date.now();
  const dateTime = date.getTime();
  return (now - dateTime) / (1000 * 60 * 60 * 24);
}

/**
 * Format age in days as a human-readable string.
 *
 * @param {number} days
 * @returns {string}
 */
export function formatAge(days) {
  return Math.floor(days) === 1 ? '1 day' : `${Math.floor(days)} days`;
}

// --- Directory filtering and cleanup ---

/**
 * Get list of directories in a path that match the YYYY-MM-DD_* pattern.
 *
 * @param {string} outputDir
 * @returns {Array<{ name: string, date: Date, age: number }>}
 */
export function getMatchingDirs(outputDir) {
  let entries;
  try {
    entries = readdirSync(outputDir);
  } catch (err) {
    return [];
  }

  const matching = [];
  for (const entry of entries) {
    const fullPath = join(outputDir, entry);
    try {
      const stat = statSync(fullPath);
      if (stat.isDirectory()) {
        const date = parseDateFromDirName(entry);
        if (date !== null) {
          const age = calculateAgeDays(date);
          matching.push({ name: entry, date, age });
        }
      }
    } catch (err) {
      // Skip entries that can't be stat'd
    }
  }
  return matching;
}

/**
 * Filter directories by age threshold.
 *
 * @param {Array<{ name: string, date: Date, age: number }>} dirs
 * @param {number} olderThanDays
 * @returns {Array<{ name: string, date: Date, age: number }>}
 */
export function filterOldDirs(dirs, olderThanDays) {
  return dirs.filter(dir => dir.age > olderThanDays);
}

/**
 * Execute cleanup: remove old directories or log what would be removed.
 *
 * @param {string} outputDir
 * @param {number} olderThanDays
 * @param {boolean} dryRun
 * @returns {{ removed: number, remaining: number }}
 */
export function cleanup(outputDir, olderThanDays, dryRun) {
  const allDirs = getMatchingDirs(outputDir);
  const oldDirs = filterOldDirs(allDirs, olderThanDays);

  for (const dir of oldDirs) {
    const fullPath = join(outputDir, dir.name);
    const ageStr = formatAge(dir.age);

    if (dryRun) {
      process.stdout.write(`Would remove: ${join(basename(outputDir), dir.name)} (${ageStr} old)\n`);
    } else {
      try {
        rmSync(fullPath, { recursive: true, force: true });
        process.stdout.write(`Removed: ${join(basename(outputDir), dir.name)} (${ageStr} old)\n`);
      } catch (err) {
        process.stderr.write(`Error removing ${dir.name}: ${err.message}\n`);
      }
    }
  }

  const remaining = allDirs.length - oldDirs.length;
  const action = dryRun ? 'Would remove' : 'Removed';
  process.stdout.write(`${action} ${oldDirs.length} ${oldDirs.length === 1 ? 'directory' : 'directories'} (${remaining} remaining)\n`);

  return { removed: oldDirs.length, remaining };
}

// --- Main entry point ---

function printUsage() {
  process.stderr.write(
    'Usage: node scripts/clean-output.mjs [--older-than <days>] [--dry-run] [--output-dir <path>]\n'
  );
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  const olderThanDays = args.olderThan === undefined ? 30 : parseInt(args.olderThan, 10);
  const dryRun = args.dryRun === true;
  const outputDir = args.outputDir === undefined
    ? resolve(dirname(__dirname), 'output')
    : resolve(args.outputDir);

  if (Number.isNaN(olderThanDays) || olderThanDays < 0) {
    process.stderr.write('Error: --older-than must be a non-negative number\n');
    printUsage();
    process.exit(1);
  }

  cleanup(outputDir, olderThanDays, dryRun);
}

// Only run main when executed directly (not when imported by tests)
if (process.argv[1] === new URL(import.meta.url).pathname) {
  main().catch(err => {
    process.stderr.write(`${err.message}\n`);
    process.exit(1);
  });
}
