import { spawn, ChildProcess } from 'child_process'
import { join, resolve } from 'path'
import { existsSync } from 'fs'
import { app } from 'electron'
import * as net from 'net'

export class MCNServer {
  private process: ChildProcess | null = null
  private port: number = 7842
  private serverPath: string
  private restartAttempts = 0
  private maxRestarts = 3
  private isShuttingDown = false

  constructor() {
    // In packaged app, web-playground is in extraResources
    // In dev, resolve relative to app root or repo root
    const isPacked = app.isPackaged
    if (isPacked) {
      this.serverPath = join(process.resourcesPath, 'web-playground')
    } else {
      const candidates = [
        join(__dirname, '../../../web-playground'),
        join(__dirname, '../../../../web-playground'),
        join(process.cwd(), '../web-playground'),
        join(process.cwd(), 'web-playground'),
        resolve(__dirname, '../../../../mcn/web-playground'),
        resolve(__dirname, '../../../mcn/web-playground')
      ]
      this.serverPath = candidates.find((p) => existsSync(join(p, 'server.py'))) || candidates[0]
    }
  }

  async start(): Promise<number> {
    this.port = await this.findFreePort(7842)
    await this.spawnServer()
    await this.waitUntilReady()
    return this.port
  }

  private findFreePort(preferred: number): Promise<number> {
    return new Promise((resolve) => {
      const server = net.createServer()
      server.once('error', () => resolve(this.findFreePort(preferred + 1)))
      server.once('listening', () => {
        const addr = server.address() as net.AddressInfo
        server.close(() => resolve(addr.port))
      })
      server.listen(preferred)
    })
  }

  private spawnServer(): Promise<void> {
    return new Promise((resolve, reject) => {
      const pythonBin = process.platform === 'win32' ? 'python' : 'python3'

      this.process = spawn(pythonBin, ['server.py', '--port', String(this.port)], {
        cwd: this.serverPath,
        env: { ...process.env, MCN_DESKTOP: '1', MCN_PLAYGROUND_PORT: String(this.port) },
        stdio: ['ignore', 'pipe', 'pipe']
      })

      this.process.stdout?.on('data', (data: Buffer) => {
        console.log('[MCN Server]', data.toString().trim())
      })

      this.process.stderr?.on('data', (data: Buffer) => {
        console.error('[MCN Server Error]', data.toString().trim())
      })

      this.process.on('spawn', () => resolve())

      this.process.on('error', (err) => {
        console.error('[MCN Server] Failed to spawn:', err.message)
        reject(err)
      })

      this.process.on('exit', (code, signal) => {
        if (!this.isShuttingDown && this.restartAttempts < this.maxRestarts) {
          console.warn(
            `MCN server exited (code=${code}, signal=${signal}), restarting... ` +
            `(attempt ${++this.restartAttempts}/${this.maxRestarts})`
          )
          setTimeout(() => this.spawnServer().catch(console.error), 2000)
        }
      })
    })
  }

  private waitUntilReady(timeout = 15000): Promise<void> {
    return new Promise((resolve, reject) => {
      const start = Date.now()
      const check = async (): Promise<void> => {
        try {
          const http = await import('http')
          await new Promise<void>((res, rej) => {
            const req = http.default.get(
              `http://localhost:${this.port}/api/health`,
              (response) => {
                if (response.statusCode === 200) res()
                else rej(new Error(`status ${response.statusCode}`))
              }
            )
            req.on('error', rej)
            req.end()
          })
          resolve()
        } catch {
          if (Date.now() - start > timeout) {
            reject(new Error(`MCN server did not become ready within ${timeout}ms`))
          } else {
            setTimeout(check, 500)
          }
        }
      }
      check()
    })
  }

  stop(): void {
    this.isShuttingDown = true
    if (this.process) {
      this.process.kill('SIGTERM')
      this.process = null
    }
  }
}
