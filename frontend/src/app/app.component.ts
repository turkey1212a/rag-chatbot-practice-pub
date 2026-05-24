import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

type DocumentSummary = {
  document_id: string;
  file_name: string;
  page_count: number;
  stored_pages: number;
};

type IngestResponse = {
  file_name: string;
  page_count: number;
  stored_pages: number;
  skipped_pages: number[];
};

type ReferencePage = {
  pdf_name: string;
  page_number: number;
  excerpt: string;
  similarity_score: number;
};

type ChatResponse = {
  answer: string;
  references: ReferencePage[];
};

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css'],
})
export class AppComponent implements OnInit {
  readonly documents = signal<DocumentSummary[]>([]);
  readonly answer = signal('');
  readonly references = signal<ReferencePage[]>([]);
  readonly status = signal('');
  readonly error = signal('');
  readonly uploading = signal(false);
  readonly asking = signal(false);

  question = '';
  selectedFile: File | null = null;

  private readonly apiBase =
    window.location.port === '4200' ? 'http://localhost:8000' : '/api';

  constructor(private readonly http: HttpClient) {}

  ngOnInit(): void {
    this.loadDocuments();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile = input.files?.[0] ?? null;
    this.error.set('');
  }

  uploadPdf(): void {
    if (!this.selectedFile || this.uploading()) {
      return;
    }

    const formData = new FormData();
    formData.append('file', this.selectedFile);

    this.uploading.set(true);
    this.status.set('PDFを取り込んでいます...');
    this.error.set('');

    this.http.post<IngestResponse>(`${this.apiBase}/documents/upload`, formData).subscribe({
      next: (response) => {
        const skipped =
          response.skipped_pages.length > 0
            ? ` スキップ: ${response.skipped_pages.join(', ')}ページ`
            : '';
        this.status.set(
          `${response.file_name} を取り込みました。${response.stored_pages}/${response.page_count}ページを保存しました。${skipped}`,
        );
        this.selectedFile = null;
        this.loadDocuments();
      },
      error: (error) => {
        this.error.set(error?.error?.detail ?? 'PDFの取り込みに失敗しました。');
        this.uploading.set(false);
      },
      complete: () => {
        this.uploading.set(false);
      },
    });
  }

  ask(): void {
    const question = this.question.trim();
    if (!question || this.asking()) {
      return;
    }

    this.asking.set(true);
    this.answer.set('');
    this.references.set([]);
    this.status.set('資料を検索して回答を生成しています...');
    this.error.set('');

    this.http
      .post<ChatResponse>(`${this.apiBase}/chat`, {
        question,
        limit: 5,
      })
      .subscribe({
        next: (response) => {
          this.answer.set(response.answer);
          this.references.set(response.references);
          this.status.set('');
        },
        error: (error) => {
          this.error.set(error?.error?.detail ?? '回答生成に失敗しました。');
          this.status.set('');
          this.asking.set(false);
        },
        complete: () => {
          this.asking.set(false);
        },
      });
  }

  private loadDocuments(): void {
    this.http.get<DocumentSummary[]>(`${this.apiBase}/documents`).subscribe({
      next: (documents) => {
        this.documents.set(documents);
      },
      error: () => {
        this.error.set('資料一覧を取得できませんでした。');
      },
    });
  }
}
