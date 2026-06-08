package com.mercadez.service;

import com.mercadez.dto.*;
import com.mercadez.exception.*;
import com.mercadez.model.Usuario;
import com.mercadez.repository.UsuarioRepository;
import com.mercadez.security.JwtService;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class UsuarioService {

    private final UsuarioRepository repo;
    private final PasswordEncoder   encoder;
    private final JwtService        jwt;

    public UsuarioService(UsuarioRepository repo, PasswordEncoder encoder, JwtService jwt) {
        this.repo    = repo;
        this.encoder = encoder;
        this.jwt     = jwt;
    }

    @Transactional
    public UsuarioResponse cadastrar(CadastroUsuarioRequest req) {
        if (repo.existsByEmail(req.getEmail())) {
            throw new NegocioException("Email já cadastrado.");
        }
        if (req.getCpf() != null && !req.getCpf().isBlank() && repo.existsByCpf(req.getCpf())) {
            throw new NegocioException("CPF já cadastrado.");
        }

        Usuario u = Usuario.builder()
                .nome(req.getNome())
                .email(req.getEmail().toLowerCase())
                .senha(encoder.encode(req.getSenha()))
                .cpf(req.getCpf())
                .build();

        return UsuarioResponse.de(repo.save(u));
    }

    @Transactional(readOnly = true)
    public LoginResponse login(LoginRequest req) {
        Usuario u = repo.findByEmail(req.getEmail().toLowerCase())
                .orElseThrow(CredenciaisInvalidasException::new);

        if (!encoder.matches(req.getSenha(), u.getSenha())) {
            throw new CredenciaisInvalidasException();
        }

        String token = jwt.gerarToken(u.getId(), u.getEmail(), "CLIENTE");
        return new LoginResponse(token, "Bearer", u.getPerfil().name(), u.getId(), u.getNome(), u.getEmail());
    }

    @Transactional(readOnly = true)
    public UsuarioResponse buscarPorId(Long id) {
        return UsuarioResponse.de(
                repo.findById(id).orElseThrow(() -> new NaoEncontradoException("Usuário não encontrado."))
        );
    }
}
