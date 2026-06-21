import React, { useCallback } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { cn } from '../utils/cn';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';

interface UIButtonProps {
    text: string;
    onClick?: () => void;
    className?: string;
    disabled?: boolean;
}

export function UIButton({ text, onClick, className = '', disabled = false }: UIButtonProps) {
    const handleClick = useCallback(() => {
        if (!disabled && onClick) {
            onClick();
        }
    }, [disabled, onClick]);

    return (
        <Button 
            className={cn(className)}
            onClick={handleClick}
            disabled={disabled}
            aria-label={text}
        >
            {text}
        </Button>
    );
}

interface UIInputProps {
    placeholder?: string;
    onChange?: (value: string) => void;
    className?: string;
    type?: string;
}

export function UIInput({ placeholder = '', onChange, className = '', type = 'text' }: UIInputProps) {
    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        if (onChange) {
            onChange(e.target.value);
        }
    }, [onChange]);

    return (
        <Input
            type={type}
            placeholder={placeholder}
            className={cn(className)}
            onChange={handleChange}
            aria-label={placeholder || 'Input field'}
        />
    );
}

interface UITextProps {
    content: string;
    tag?: keyof JSX.IntrinsicElements;
    className?: string;
}

export function UIText({ content, tag: Tag = 'p', className = 'text' }: UITextProps) {
    return <Tag className={className}>{content}</Tag>;
}

interface UIContainerProps {
    children: React.ReactNode;
    className?: string;
}

export function UIContainer({ children, className = 'container' }: UIContainerProps) {
    return <div className={className}>{children}</div>;
}

interface UIFormProps {
    children: React.ReactNode;
    onSubmit?: () => void;
    className?: string;
}

export function UIForm({ children, onSubmit, className = 'form' }: UIFormProps) {
    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSubmit?.();
    };
    
    return (
        <form onSubmit={handleSubmit} className={className}>
            {children}
        </form>
    );
}

interface UITableProps {
    columns: string[];
    data: any[];
    className?: string;
}

export function UITable({ columns, data, className = '' }: UITableProps) {
    if (!Array.isArray(data) || !Array.isArray(columns)) {
        return (
            <Card className={cn('p-4', className)}>
                <CardContent className="text-center text-muted-foreground">
                    No data available
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className={cn(className)}>
            <Table>
                <TableHeader>
                    <TableRow>
                        {columns.map((column, index) => (
                            <TableHead key={`header-${index}`}>
                                {column}
                            </TableHead>
                        ))}
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {data.map((row, rowIndex) => (
                        <TableRow key={`row-${rowIndex}`}>
                            {columns.map((column, colIndex) => (
                                <TableCell key={`cell-${rowIndex}-${colIndex}`}>
                                    {row[column.toLowerCase()] || row[column] || '-'}
                                </TableCell>
                            ))}
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </Card>
    );
}

interface UIChartProps {
    type: 'bar' | 'line';
    data: any[];
    className?: string;
}

export function UIChart({ type, data, className = '' }: UIChartProps) {
    const ChartComponent = type === 'bar' ? BarChart : LineChart;
    const DataComponent = type === 'bar' ? Bar : Line;
    
    return (
        <Card className={cn(className)}>
            <CardContent className="p-6">
                <div className="w-full h-64">
                    <ResponsiveContainer width="100%" height="100%">
                        <ChartComponent data={data}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" />
                            <YAxis />
                            <Tooltip />
                            <Legend />
                            <DataComponent dataKey="value" fill="hsl(var(--primary))" stroke="hsl(var(--primary))" />
                        </ChartComponent>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
    );
}
