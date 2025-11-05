import React from 'react';
import { Pressable, PressableProps, StyleSheet, Text } from 'react-native';
import { colors, spacing, fontFamilies, fontSizes } from '../tokens';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost';

interface ButtonProps extends PressableProps {
  label: string;
  variant?: ButtonVariant;
}

export const Button: React.FC<ButtonProps> = ({ label, variant = 'primary', style, disabled, ...props }) => {
  const { container, label: labelStyle } = styles[variant];

  return (
    <Pressable
      style={[container, disabled ? disabledStyle : null, style]}
      accessibilityState={{ disabled }}
      disabled={disabled}
      {...props}
    >
      <Text style={labelStyle}>{label}</Text>
    </Pressable>
  );
};

const baseContainer = {
  paddingVertical: spacing.sm,
  paddingHorizontal: spacing.lg,
  borderRadius: 999,
  alignItems: 'center' as const
};

const baseLabel = {
  fontFamily: fontFamilies.medium,
  fontSize: fontSizes.body,
  color: colors.text,
  letterSpacing: 0.4
};

const styles = {
  primary: StyleSheet.create({
    container: {
      ...baseContainer,
      backgroundColor: colors.primary
    },
    label: {
      ...baseLabel,
      color: '#FFFFFF'
    }
  }),
  secondary: StyleSheet.create({
    container: {
      ...baseContainer,
      backgroundColor: colors.surface,
      borderWidth: 1,
      borderColor: colors.border
    },
    label: {
      ...baseLabel
    }
  }),
  ghost: StyleSheet.create({
    container: {
      ...baseContainer,
      backgroundColor: 'transparent'
    },
    label: {
      ...baseLabel,
      color: colors.primary
    }
  })
} as const;

const disabledStyle = {
  opacity: 0.6
};
