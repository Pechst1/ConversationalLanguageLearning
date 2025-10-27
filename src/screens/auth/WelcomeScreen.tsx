import React from 'react';
import { StyleSheet, Text, View, TouchableOpacity } from 'react-native';

type WelcomeScreenProps = {
  onLoginPress: () => void;
  onRegisterPress: () => void;
};

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ onLoginPress, onRegisterPress }) => {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Bienvenue!</Text>
      <Text style={styles.subtitle}>
        Practise French conversations, track your progress, and stay motivated every day.
      </Text>
      <TouchableOpacity accessibilityRole="button" style={styles.primaryButton} onPress={onLoginPress}>
        <Text style={styles.primaryButtonLabel}>Log in</Text>
      </TouchableOpacity>
      <TouchableOpacity accessibilityRole="button" style={styles.secondaryButton} onPress={onRegisterPress}>
        <Text style={styles.secondaryButtonLabel}>Create account</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
    backgroundColor: '#ffffff',
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    marginBottom: 12,
    color: '#2d2d2d',
  },
  subtitle: {
    fontSize: 16,
    lineHeight: 22,
    color: '#4f4f4f',
    marginBottom: 32,
  },
  primaryButton: {
    backgroundColor: '#0066ff',
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 16,
  },
  primaryButtonLabel: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: '600',
  },
  secondaryButton: {
    backgroundColor: 'transparent',
    paddingVertical: 14,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: '#0066ff',
    alignItems: 'center',
  },
  secondaryButtonLabel: {
    color: '#0066ff',
    fontSize: 18,
    fontWeight: '600',
  },
});
