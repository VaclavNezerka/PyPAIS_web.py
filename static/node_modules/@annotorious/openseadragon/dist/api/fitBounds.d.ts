import { Annotation, ImageAnnotationStore } from '@annotorious/annotorious';
import { default as OpenSeadragon } from 'openseadragon';
export interface FitboundsOptions {
    immediately?: boolean;
    padding?: number | [number, number, number, number];
}
export declare const fitBounds: <I extends Annotation>(viewer: OpenSeadragon.Viewer, store: ImageAnnotationStore<I>) => (arg: {
    id: string;
} | string, opts?: FitboundsOptions) => void;
export declare const fitBoundsWithConstraints: <I extends Annotation>(viewer: OpenSeadragon.Viewer, store: ImageAnnotationStore<I>) => (arg: {
    id: string;
} | string, opts?: FitboundsOptions) => void;
