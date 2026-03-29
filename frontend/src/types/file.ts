// File Browser Types

export interface FileNode {
  name: string
  type: 'directory' | 'file'
  path: string
  has_children?: boolean  // Only for directories
  size?: number           // Only for files
  language?: string       // Only for files
}

export interface TreeResponse {
  nodes: FileNode[]
}

export interface TextFileContent {
  type: 'text'
  content: string
  language: string
  size: number
}

export interface ImageFileContent {
  type: 'image'
  mime_type: string
  size: number
}

export interface TooLargeFileContent {
  type: 'too_large'
  size: number
  message: string
}

export interface BinaryFileContent {
  type: 'binary'
  size: number
  message: string
}

export type FileContent = TextFileContent | ImageFileContent | TooLargeFileContent | BinaryFileContent

export interface FileBrowserState {
  selectedPath: string | null
  expandedPaths: Set<string>
  treeCache: Map<string, FileNode[]>
  fileContent: FileContent | null
  loading: boolean
  error: string | null
}