import { ref, reactive } from 'vue'
import type { FileNode, TreeResponse, FileContent } from '@/types/file'

const API_BASE = '/api/workspaces'

export function useFileBrowser(workspaceId: string) {
  // State
  const selectedPath = ref<string | null>(null)
  const expandedPaths = reactive(new Set<string>())
  const treeCache = reactive(new Map<string, FileNode[]>())
  const fileContent = ref<FileContent | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Fetch directory tree
  async function fetchTree(path: string = ''): Promise<FileNode[]> {
    // Check cache first
    if (treeCache.has(path)) {
      return treeCache.get(path)!
    }

    loading.value = true
    error.value = null

    try {
      const url = path
        ? `${API_BASE}/${workspaceId}/tree/?path=${encodeURIComponent(path)}`
        : `${API_BASE}/${workspaceId}/tree/`

      const response = await fetch(url, { credentials: 'include' })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.error || 'Failed to fetch directory tree')
      }

      const data: TreeResponse = await response.json()
      treeCache.set(path, data.nodes)
      return data.nodes
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      return []
    } finally {
      loading.value = false
    }
  }

  // Fetch file content
  async function fetchFileContent(path: string): Promise<FileContent | null> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(
        `${API_BASE}/${workspaceId}/files/${encodeURIComponent(path)}`,
        { credentials: 'include' }
      )

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.error || 'Failed to fetch file content')
      }

      const data: FileContent = await response.json()
      fileContent.value = data
      selectedPath.value = path
      return data
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      fileContent.value = null
      return null
    } finally {
      loading.value = false
    }
  }

  // Get raw file URL (for images and downloads)
  function getRawFileUrl(path: string): string {
    return `${API_BASE}/${workspaceId}/files/${encodeURIComponent(path)}?raw=1`
  }

  // Expand directory
  async function expandDirectory(path: string): Promise<FileNode[]> {
    expandedPaths.add(path)
    return await fetchTree(path)
  }

  // Collapse directory
  function collapseDirectory(path: string): void {
    expandedPaths.delete(path)
  }

  // Toggle directory expansion
  async function toggleDirectory(path: string): Promise<FileNode[]> {
    if (expandedPaths.has(path)) {
      collapseDirectory(path)
      return []
    } else {
      return await expandDirectory(path)
    }
  }

  // Select file
  async function selectFile(path: string): Promise<FileContent | null> {
    return await fetchFileContent(path)
  }

  // Clear state
  function clearState(): void {
    selectedPath.value = null
    expandedPaths.clear()
    treeCache.clear()
    fileContent.value = null
    error.value = null
  }

  return {
    // State
    selectedPath,
    expandedPaths,
    treeCache,
    fileContent,
    loading,
    error,

    // Actions
    fetchTree,
    fetchFileContent,
    getRawFileUrl,
    expandDirectory,
    collapseDirectory,
    toggleDirectory,
    selectFile,
    clearState,
  }
}