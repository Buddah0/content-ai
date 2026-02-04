
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
            <Card className="p-8 flex flex-col items-center justify-center gap-4 border border-neon-cyan/30 bg-glass/40 backdrop-blur-sm shadow-glow-cyan">
                <div className="p-4 rounded-full bg-neon-cyan/10 text-neon-cyan">
                    <FileVideo className="w-8 h-8 drop-shadow-[0_0_8px_hsl(var(--neon-cyan)/0.5)]" />
                </div>
                <div className="text-center">
                    <p className="font-medium text-lg">{selectedFile.name}</p>
                    <p className="text-sm text-muted-foreground">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</p>
                </div>
                <Button variant="outline" onClick={onClear} className="mt-2 border-glass-border hover:border-neon-blue/40 hover:bg-neon-blue/5 transition-all">
                    <X className="w-4 h-4 mr-2" />
                    Change Video
                </Button>
            </Card>
        )
    }

    return (
        <Card
            className={cn(
                "p-12 border-2 border-dashed transition-all duration-300 cursor-pointer flex flex-col items-center justify-center gap-4 text-center bg-glass/30 backdrop-blur-sm",
                isDragging
                    ? "border-neon-blue bg-neon-blue/10 shadow-glow-blue"
                    : "border-glass-border hover:border-neon-blue/50 hover:shadow-glow-sm"
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
            <div className={cn(
                "p-4 rounded-full transition-all duration-300",
                isDragging
                    ? "bg-neon-blue/20 text-neon-blue shadow-glow-sm"
                    : "bg-glass/50 text-muted-foreground"
            )}>
                <Upload className={cn(
                    "w-8 h-8 transition-all duration-300",
                    isDragging && "drop-shadow-[0_0_10px_hsl(var(--neon-blue)/0.6)]"
                )} />
            </div>
            <div className="space-y-1">
                <p className="font-medium text-lg">Drop video here or click to upload</p>
                <p className="text-sm text-muted-foreground">Supports MP4, MOV, MKV</p>
            </div>
        </Card>
    );
}
