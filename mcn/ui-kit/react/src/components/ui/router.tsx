import * as React from "react"
import { cn } from "@/lib/utils"

/* A small hash router (#/path). Hash URLs work identically in an exported app,
   on static hosting and inside Studio's preview frame, with no server rules. */

function currentPath(): string {
  const h = typeof window === "undefined" ? "" : window.location.hash.replace(/^#/, "")
  return h.startsWith("/") ? h.split("?")[0] : "/"
}

const RouterContext = React.createContext<{ path: string; navigate: (to: string) => void }>({
  path: "/", navigate: () => {},
})

export function Router({ children }: { children?: React.ReactNode }) {
  const [path, setPath] = React.useState(currentPath)
  React.useEffect(() => {
    const onChange = () => setPath(currentPath())
    window.addEventListener("hashchange", onChange)
    return () => window.removeEventListener("hashchange", onChange)
  }, [])
  const navigate = React.useCallback((to: string) => { window.location.hash = to }, [])
  return <RouterContext.Provider value={{ path, navigate }}>{children}</RouterContext.Provider>
}

/** For code written against react-router. */
export const BrowserRouter = Router
export const HashRouter = Router

export function useLocation() { return { pathname: React.useContext(RouterContext).path } }
export function useNavigate() { return React.useContext(RouterContext).navigate }

function matches(pattern: string, path: string): boolean {
  if (pattern === "*" ) return true
  const a = pattern.replace(/\/$/, "").split("/"), b = path.replace(/\/$/, "").split("/")
  return a.length === b.length && a.every((seg, i) => seg.startsWith(":") || seg === b[i])
}

export function Route(_: { path: string; element: React.ReactNode }) { return null }

/** Renders the first <Route> whose path matches; "*" matches anything. */
export function Routes({ children }: { children?: React.ReactNode }) {
  const { path } = React.useContext(RouterContext)
  let found: React.ReactNode = null
  React.Children.forEach(children, (child) => {
    if (found || !React.isValidElement(child)) return
    const props = child.props as { path: string; element: React.ReactNode }
    if (matches(props.path, path)) found = props.element
  })
  return <>{found}</>
}

export interface NavLinkProps extends Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "className"> {
  to: string
  className?: string | ((state: { isActive: boolean }) => string)
}

export function NavLink({ to, className, children, ...props }: NavLinkProps) {
  const { path } = React.useContext(RouterContext)
  const isActive = path === to || (to !== "/" && path.startsWith(to + "/"))
  const cls = typeof className === "function" ? className({ isActive }) : cn(className, isActive && "active")
  return <a href={"#" + to} className={cls} aria-current={isActive ? "page" : undefined} {...props}>{children}</a>
}

export const Link = NavLink
