"""
Simple RAG system using OpenAI embeddings
"""
import numpy as np
from typing import List, Dict
from openai import OpenAI


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


class SimpleRAG:
    """Simple RAG system using OpenAI embeddings and in-memory vector store."""
    
    def __init__(self, gemini_client: OpenAI, embedding_model: str = "gemini-embedding-001"):
        self.client = gemini_client
        self.embedding_model = embedding_model
        self.chunks: List[str] = []
        self.chunk_metadata: List[Dict] = []
        self.embeddings: np.ndarray = None
        
    def add_documents(self, documents: Dict[str, str], chunk_size: int = 500, overlap: int = 50):
        """
        Add documents to the knowledge base.
        
        Args:
            documents: Dictionary mapping document names to their content
            chunk_size: Number of words per chunk
            overlap: Number of words to overlap between chunks
        """
        all_chunks = []
        all_metadata = []
        
        for doc_name, content in documents.items():
            chunks = chunk_text(content, chunk_size, overlap)
            for idx, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadata.append({
                    "source": doc_name,
                    "chunk_index": idx,
                    "total_chunks": len(chunks)
                })
        
        self.chunks = all_chunks
        self.chunk_metadata = all_metadata
        
        # Create embeddings for all chunks
        print(f"Creating embeddings for {len(all_chunks)} chunks...")
        embeddings_list = []
        batch_size = 100
        
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=batch
            )
            batch_embeddings = [item.embedding for item in response.data]
            embeddings_list.extend(batch_embeddings)
        
        self.embeddings = np.array(embeddings_list)
        print(f"RAG system initialized with {len(all_chunks)} chunks")
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Retrieve the most relevant chunks for a query.
        
        Args:
            query: The search query
            top_k: Number of top results to return
            
        Returns:
            List of dictionaries containing chunk text and metadata
        """
        if len(self.chunks) == 0:
            return []
        
        # Get query embedding
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=[query]
        )
        query_embedding = np.array(response.data[0].embedding)
        
        # Calculate similarities
        similarities = []
        for i, chunk_embedding in enumerate(self.embeddings):
            similarity = cosine_similarity(query_embedding, chunk_embedding)
            similarities.append((i, similarity))
        
        # Sort by similarity and get top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_indices = [idx for idx, _ in similarities[:top_k]]
        
        # Return results with metadata
        results = []
        for idx in top_indices:
            results.append({
                "text": self.chunks[idx],
                "source": self.chunk_metadata[idx]["source"],
                "chunk_index": self.chunk_metadata[idx]["chunk_index"],
                "similarity": similarities[top_indices.index(idx)][1]
            })
        
        return results
