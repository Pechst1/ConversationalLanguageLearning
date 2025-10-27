import React from 'react';
import { Text as RNText, TextProps as RNTextProps, StyleSheet } from 'react-native';
import { colors, fontFamilies, fontSizes, lineHeights } from '../tokens';

export type TextVariant = 'caption' | 'body' | 'subtitle' | 'title' | 'headline';

export interface TextProps extends RNTextProps {
  variant?: TextVariant;
  emphasis?: 'regular' | 'medium' | 'bold';
  color?: keyof typeof colors;
}

export const Text: React.FC<TextProps> = ({
  variant = 'body',
  emphasis = 'regular',
  color: colorName = 'text',
  style,
  children,
  ...props
}) => {
  return (
    <RNText
      style={[
        baseStyles.text,
        variantStyles[variant],
        emphasisStyles[emphasis],
        { color: colors[colorName] },
        style
      ]}
      {...props}
    >
      {children}
    </RNText>
  );
};

const baseStyles = StyleSheet.create({
  text: {
    fontFamily: fontFamilies.regular,
    color: colors.text
  }
});

const variantStyles = StyleSheet.create({
  caption: {
    fontSize: fontSizes.caption,
    lineHeight: fontSizes.caption * lineHeights.tight
  },
  body: {
    fontSize: fontSizes.body,
    lineHeight: fontSizes.body * lineHeights.normal
  },
  subtitle: {
    fontSize: fontSizes.subtitle,
    lineHeight: fontSizes.subtitle * lineHeights.normal
  },
  title: {
    fontSize: fontSizes.title,
    lineHeight: fontSizes.title * lineHeights.normal
  },
  headline: {
    fontSize: fontSizes.headline,
    lineHeight: fontSizes.headline * lineHeights.relaxed
  }
});

const emphasisStyles = StyleSheet.create({
  regular: {
    fontFamily: fontFamilies.regular
  },
  medium: {
    fontFamily: fontFamilies.medium
  },
  bold: {
    fontFamily: fontFamilies.bold
  }
});
