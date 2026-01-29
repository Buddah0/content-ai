
import React, { useCallback, useState } from 'react';
import { Upload, FileVideo, X } from 'lucide-react';
import { Card } from './ui/card';
import { cn } from '@/lib/utils';
import { Button } from './ui/button';

interface UploadZoneProps {
    onFileSelect: (file: File) => void;
    selectedFile: File | null;
    onClear: () => void;
}

export function UploadZone({ onFileSelect, selectedFile, onClear }: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false);

    const handleDrag = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setIsDragging(true);
        } else if (e.type === 'dragleave') {
            setIsDragging(false);
        }
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const file = e.dataTransfer.files[0];
            if (file.type.startsWith('video/')) {
                onFileSelect(file);
            } else {
                alert("Please upload a video file.");
            }
        }
    }, [onFileSelect]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            onFileSelect(e.target.files[0]);
        }
    };

    if (selectedFile) {
        return (
            <Card className="p-8 flex flex-col items-center justify-center gap-4 border-2 border-primary/20 bg-primary/5">
                <div className="p-4 rounded-full bg-primary/10 text-primary">
                    <FileVideo className="w-8 h-8" />
                </div>
                <div className="text-center">
                    <p className="font-medium text-lg">{selectedFile.name}</p>
                    <p className="text-sm text-muted-foreground">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</p>
                </div>
                <Button variant="outline" onClick={onClear} className="mt-2">
                    <X className="w-4 h-4 mr-2" />
                    Change Video
                </Button>
            </Card>
        )
    }

    return (
        <Card
            className={cn(
                "p-12 border-2 border-dashed transition-colors cursor-pointer flex flex-col items-center justify-center gap-4 text-center",
                isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/50"
            )}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => document.getElementById('file-upload')?.click()}
        >
            <input
                type="file"
                id="file-upload"
                className="hidden"
                accept="video/*"
                onChange={handleChange}
            />
            <div className="p-4 rounded-full bg-secondary text-secondary-foreground group-hover:scale-110 transition-transform">
                <Upload className="w-8 h-8" />
            </div>
            <div className="space-y-1">
                <p className="font-medium text-lg">Drop video here or click to upload</p>
                <p className="text-sm text-muted-foreground">Supports MP4, MOV, MKV</p>
            </div>
        </Card>
    );
}
