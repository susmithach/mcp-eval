import { execFile } from "child_process";

export interface ProcessResult {
  exitCode: number;
  stdout: string;
  stderr: string;
}

/**
 * Runs a command (no shell) with a hard timeout and cwd restriction.
 * Always resolves — never rejects.
 */
export async function runProcess(
  command: string,
  args: string[],
  cwd: string,
  timeoutMs = 30_000
): Promise<ProcessResult> {
  return new Promise((resolve) => {
    execFile(
      command,
      args,
      {
        cwd,
        timeout: timeoutMs,
        maxBuffer: 2 * 1024 * 1024, // 2 MB
        shell: false,
      },
      (error, stdout, stderr) => {
        if (error) {
          resolve({
            exitCode: (error as NodeJS.ErrnoException & { code?: number }).code
              ?? 1,
            stdout: stdout ?? "",
            stderr: stderr || error.message,
          });
        } else {
          resolve({ exitCode: 0, stdout, stderr });
        }
      }
    );
  });
}
